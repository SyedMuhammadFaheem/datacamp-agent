import json

from dcai.adapters import selectors


def test_monaco_set_script_embeds_code_as_a_json_string_literal():
    code = 'print("it\'s {x}")\n# tab\t  \U0001f600 \\n'
    js = selectors.JS_SET_MONACO_VALUE.format(code=json.dumps(code))
    assert f"model.setValue({json.dumps(code)});" in js
    # the script must remain a single well-formed IIFE after formatting
    assert js.strip().startswith("(() => {") and js.strip().endswith("})()")
