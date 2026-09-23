import ast
from pathlib import Path


def test_saved_mode_transition_is_consumed_before_widget_creation():
    tree = ast.parse((Path(__file__).parents[1] / "app_pages/osp_inspections.py").read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_apply_saved_mode")
    namespace = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "transition", "exec"), namespace)
    key = "osp_DIMENSIONAL_OSP_SAMPLE_mode"
    state = {key: "Pending / New", key + "_after_save": True}
    namespace["_apply_saved_mode"](state, key)
    assert state == {key: "Edit Existing"}
    state[key] = "Pending / New"
    namespace["_apply_saved_mode"](state, key)
    assert state[key] == "Pending / New"
