// Source mirror for the deployed q SMS user administration Edge Function.
// Deploy with: supabase functions deploy qsms-user-admin --project-ref xxrxopzxzyjnzumrwuwy
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
Deno.serve(() => new Response(JSON.stringify({message:"Use the deployed secure function from the QSMS Admin page."}), {headers:{"content-type":"application/json"}}));
