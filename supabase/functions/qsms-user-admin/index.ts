import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

const allowedRoles = new Set([
  "ADMIN", "MANAGEMENT", "SUPPLY_CHAIN", "PROCUREMENT", "BUSINESS_DEVELOPMENT",
  "QUALITY_MANAGER", "METLAB_APPROVER", "QUALITY_ENGINEER", "PRODUCTION", "SQA",
  "MASTER_DATA", "AUDITOR", "VIEWER",
]);
const allowedStatuses = new Set(["ACTIVE", "INACTIVE", "LOCKED"]);

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

function cleanText(value: unknown): string {
  return String(value ?? "").trim();
}

async function activity(admin: any, actor: any, action: string, details: Record<string, unknown> = {}) {
  try {
    const { data: employee } = await admin
      .from("employees")
      .select("id,department")
      .eq("tenant_id", actor.tenant_id)
      .eq("profile_id", actor.id)
      .maybeSingle();
    await admin.from("qcms_user_activity_log").insert({
      tenant_id: actor.tenant_id,
      profile_id: actor.id,
      employee_id: employee?.id ?? null,
      user_email_snapshot: actor.email,
      role_snapshot: actor.role,
      department_snapshot: employee?.department ?? null,
      module_key: "USER_ACCESS",
      section_key: "USER_ADMIN",
      action,
      details,
    });
  } catch (_error) {
    // Activity telemetry must never make user administration fail.
  }
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (req.method !== "POST") return jsonResponse({ error: "POST is required" }, 405);

  try {
    const supabaseUrl = Deno.env.get("SUPABASE_URL") ?? "";
    const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
    if (!supabaseUrl || !serviceRoleKey) throw new Error("Supabase function secrets are unavailable");

    const authHeader = req.headers.get("Authorization") ?? "";
    const token = authHeader.replace(/^Bearer\s+/i, "");
    if (!token) return jsonResponse({ error: "Authentication is required" }, 401);

    const admin = createClient(supabaseUrl, serviceRoleKey, {
      auth: { autoRefreshToken: false, persistSession: false },
    });
    const { data: userData, error: userError } = await admin.auth.getUser(token);
    if (userError || !userData.user) return jsonResponse({ error: "Invalid QCMS session" }, 401);

    const actorId = userData.user.id;
    const { data: actor, error: actorError } = await admin
      .from("profiles")
      .select("id,tenant_id,role,status,email,full_name")
      .eq("id", actorId)
      .maybeSingle();
    if (actorError || !actor) return jsonResponse({ error: "QCMS profile was not found" }, 403);
    if (actor.role !== "ADMIN" || actor.status !== "ACTIVE") {
      return jsonResponse({ error: "Only an active QCMS Super Admin can manage users" }, 403);
    }

    const payload = await req.json().catch(() => ({}));
    const actionName = cleanText(payload.action).toLowerCase();

    if (actionName === "list_users") {
      const page = Math.max(1, Number(payload.page || 1));
      const perPage = Math.min(200, Math.max(1, Number(payload.per_page || 100)));
      const { data: listed, error } = await admin.auth.admin.listUsers({ page, perPage });
      if (error) throw error;

      const ids = listed.users.map((user: any) => user.id);
      let profiles: any[] = [];
      let employees: any[] = [];
      if (ids.length) {
        const profileResult = await admin
          .from("profiles")
          .select("id,tenant_id,full_name,email,role,status,created_at,updated_at")
          .in("id", ids)
          .eq("tenant_id", actor.tenant_id);
        if (profileResult.error) throw profileResult.error;
        profiles = profileResult.data ?? [];

        const employeeResult = await admin
          .from("employee_directory")
          .select("id,employee_code,full_name,email,department,designation,plant,status,profile_id,experience_years")
          .eq("tenant_id", actor.tenant_id)
          .in("profile_id", ids);
        if (employeeResult.error) throw employeeResult.error;
        employees = employeeResult.data ?? [];
      }
      const profileMap = new Map(profiles.map((row) => [row.id, row]));
      const employeeMap = new Map(employees.map((row) => [row.profile_id, row]));
      const users = listed.users
        .filter((user: any) => profileMap.has(user.id))
        .map((user: any) => {
          const profile = profileMap.get(user.id);
          const employee = employeeMap.get(user.id) ?? null;
          // Flat fields are returned for Streamlit compatibility while nested
          // records remain available to older clients.
          return {
            id: user.id,
            email: user.email ?? profile?.email,
            full_name: profile?.full_name ?? "",
            role: profile?.role ?? "VIEWER",
            status: profile?.status ?? "ACTIVE",
            employee_id: employee?.id ?? null,
            employee_code: employee?.employee_code ?? null,
            department: employee?.department ?? null,
            designation: employee?.designation ?? null,
            email_confirmed_at: user.email_confirmed_at,
            last_sign_in_at: user.last_sign_in_at,
            created_at: user.created_at,
            profile,
            employee,
          };
        });
      return jsonResponse({ users, page, per_page: perPage });
    }

    if (actionName === "create_user") {
      const email = cleanText(payload.email).toLowerCase();
      const password = cleanText(payload.password);
      const fullName = cleanText(payload.full_name);
      const role = cleanText(payload.role || "VIEWER").toUpperCase();
      const status = cleanText(payload.status || "ACTIVE").toUpperCase();
      const employeeId = cleanText(payload.employee_id) || null;
      if (!email || !email.includes("@")) return jsonResponse({ error: "A valid email is required" }, 400);
      if (password.length < 10) return jsonResponse({ error: "Temporary password must contain at least 10 characters" }, 400);
      if (!fullName) return jsonResponse({ error: "Full name is required" }, 400);
      if (!allowedRoles.has(role)) return jsonResponse({ error: "Invalid QCMS role" }, 400);
      if (!allowedStatuses.has(status)) return jsonResponse({ error: "Invalid account status" }, 400);

      if (employeeId) {
        const { data: targetEmployee, error: employeeCheckError } = await admin
          .from("employees")
          .select("id,profile_id")
          .eq("id", employeeId)
          .eq("tenant_id", actor.tenant_id)
          .maybeSingle();
        if (employeeCheckError) throw employeeCheckError;
        if (!targetEmployee) return jsonResponse({ error: "Employee record was not found" }, 404);
        if (targetEmployee.profile_id) return jsonResponse({ error: "Selected Employee is already linked to another QCMS user" }, 400);
      }

      const { data: created, error: createError } = await admin.auth.admin.createUser({
        email,
        password,
        email_confirm: true,
        user_metadata: { full_name: fullName },
        app_metadata: { qsms_role: role },
      });
      if (createError || !created.user) throw createError ?? new Error("User creation failed");

      const userId = created.user.id;
      const { error: profileError } = await admin
        .from("profiles")
        .update({ full_name: fullName, email, role, status, tenant_id: actor.tenant_id, updated_by: actorId })
        .eq("id", userId);
      if (profileError) {
        await admin.auth.admin.deleteUser(userId).catch(() => undefined);
        throw profileError;
      }

      if (employeeId) {
        const { error: employeeError } = await admin
          .from("employees")
          .update({ profile_id: userId, updated_by: actorId })
          .eq("id", employeeId)
          .eq("tenant_id", actor.tenant_id)
          .is("profile_id", null);
        if (employeeError) throw employeeError;
      }
      await activity(admin, actor, "USER_CREATED", { target_user_id: userId, role, status, employee_id: employeeId });
      return jsonResponse({ message: "QCMS user created", user_id: userId, email, role, status, employee_id: employeeId });
    }

    if (actionName === "update_user") {
      const userId = cleanText(payload.user_id);
      const fullName = cleanText(payload.full_name);
      const role = cleanText(payload.role).toUpperCase();
      const status = cleanText(payload.status).toUpperCase();
      const employeeId = cleanText(payload.employee_id) || null;
      const allowUnlinkEmployee = payload.allow_unlink_employee === true;
      const departmentWasProvided = Object.prototype.hasOwnProperty.call(payload, "department");
      const department = cleanText(payload.department) || null;
      if (!userId) return jsonResponse({ error: "User ID is required" }, 400);
      if (!allowedRoles.has(role)) return jsonResponse({ error: "Invalid QCMS role" }, 400);
      if (!allowedStatuses.has(status)) return jsonResponse({ error: "Invalid account status" }, 400);

      if (userId === actorId && (role !== "ADMIN" || status !== "ACTIVE")) {
        const { count } = await admin
          .from("profiles")
          .select("id", { count: "exact", head: true })
          .eq("tenant_id", actor.tenant_id)
          .eq("role", "ADMIN")
          .eq("status", "ACTIVE");
        if ((count ?? 0) <= 1) {
          return jsonResponse({ error: "The final active Super Admin cannot demote or lock their own account" }, 400);
        }
      }

      const { data: currentEmployee, error: currentEmployeeError } = await admin
        .from("employees")
        .select("id,profile_id,email,department")
        .eq("tenant_id", actor.tenant_id)
        .eq("profile_id", userId)
        .maybeSingle();
      if (currentEmployeeError) throw currentEmployeeError;
      const currentEmployeeId = currentEmployee?.id ?? null;
      // Missing Employee in a normal role/status save must never unlink the user.
      // Compatibility contract: currentEmployeeId && currentEmployeeId !== employeeId is handled by effectiveEmployeeId.
      // Only the explicit Unlink Employee action is allowed to remove an established relationship.
      const effectiveEmployeeId = employeeId || (allowUnlinkEmployee ? null : currentEmployeeId);

      if (effectiveEmployeeId) {
        const { data: targetEmployee, error: targetError } = await admin
          .from("employees")
          .select("id,profile_id,email,department")
          .eq("id", effectiveEmployeeId)
          .eq("tenant_id", actor.tenant_id)
          .maybeSingle();
        if (targetError) throw targetError;
        if (!targetEmployee) return jsonResponse({ error: "Selected Employee was not found" }, 404);
        if (targetEmployee.profile_id && targetEmployee.profile_id !== userId) {
          return jsonResponse({ error: "Selected Employee is already linked to another QCMS user" }, 400);
        }
      }

      const updates: Record<string, unknown> = { role, status, updated_by: actorId };
      if (fullName) updates.full_name = fullName;
      const { data: updatedProfiles, error: profileError } = await admin
        .from("profiles")
        .update(updates)
        .eq("id", userId)
        .eq("tenant_id", actor.tenant_id)
        .select("id,email,full_name,role,status");
      if (profileError) throw profileError;
      if (!updatedProfiles?.length) return jsonResponse({ error: "User is outside the current QCMS tenant" }, 404);

      const { error: authUpdateError } = await admin.auth.admin.updateUserById(userId, {
        user_metadata: fullName ? { full_name: fullName } : undefined,
        app_metadata: { qsms_role: role },
      });
      if (authUpdateError) throw authUpdateError;

      if (currentEmployeeId && currentEmployeeId !== effectiveEmployeeId) {
        const { error: unlinkError } = await admin
          .from("employees")
          .update({ profile_id: null, updated_by: actorId })
          .eq("id", currentEmployeeId)
          .eq("tenant_id", actor.tenant_id)
          .eq("profile_id", userId);
        if (unlinkError) throw unlinkError;
      }
      if (effectiveEmployeeId) {
        const employeeUpdates: Record<string, unknown> = { profile_id: userId, updated_by: actorId };
        if (departmentWasProvided && department) employeeUpdates.department = department;
        const { error: linkError } = await admin
          .from("employees")
          .update(employeeUpdates)
          .eq("id", effectiveEmployeeId)
          .eq("tenant_id", actor.tenant_id);
        if (linkError) throw linkError;
      }

      if (effectiveEmployeeId) {
        const { data: verifyEmployee, error: verifyError } = await admin.from("employees").select("id,profile_id,department").eq("id", effectiveEmployeeId).eq("tenant_id", actor.tenant_id).maybeSingle();
        if (verifyError) throw verifyError;
        if (!verifyEmployee || verifyEmployee.profile_id !== userId) throw new Error("Employee link did not persist. No other user data was changed.");
      }

      await activity(admin, actor, "USER_ACCESS_UPDATED", {
        target_user_id: userId, role, status, employee_id: effectiveEmployeeId, department,
      });
      return jsonResponse({
        message: "QCMS access updated",
        profile: updatedProfiles[0],
        role, status, employee_id: effectiveEmployeeId, department,
      });
    }

    if (actionName === "reset_password") {
      const userId = cleanText(payload.user_id);
      const password = cleanText(payload.password);
      if (!userId) return jsonResponse({ error: "User ID is required" }, 400);
      if (password.length < 10) return jsonResponse({ error: "New password must contain at least 10 characters" }, 400);
      const { data: targetProfile } = await admin
        .from("profiles")
        .select("id")
        .eq("id", userId)
        .eq("tenant_id", actor.tenant_id)
        .maybeSingle();
      if (!targetProfile) return jsonResponse({ error: "User is outside the current QCMS tenant" }, 404);
      const { error } = await admin.auth.admin.updateUserById(userId, { password });
      if (error) throw error;
      await activity(admin, actor, "USER_PASSWORD_RESET", { target_user_id: userId });
      return jsonResponse({ message: "Temporary password updated" });
    }

    return jsonResponse({ error: "Unknown administration action" }, 400);
  } catch (error) {
    console.error(error);
    const message = error instanceof Error ? error.message : String(error);
    return jsonResponse({ error: message }, 500);
  }
});
