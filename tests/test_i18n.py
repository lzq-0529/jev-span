from jevspan.schema import DEFAULT_SCHEMA, DEFAULT_SCHEMA_EN, detect_lang
from jevspan.web import presets


def test_detect_lang():
    assert detect_lang("Tim Cook announced that Apple will open a new office.") == "en"
    assert detect_lang("马云创办了 Alibaba") == "zh"
    assert detect_lang("2024-01-01") == "en"


def test_default_schemas_share_type_names():
    assert DEFAULT_SCHEMA.names == DEFAULT_SCHEMA_EN.names
    assert [t.title for t in DEFAULT_SCHEMA_EN.types] == ["Person", "Organization", "Address"]


def test_presets_match_across_languages():
    zh, en = presets("zh"), presets("en")
    assert zh.keys() == en.keys()
    for key in zh:
        assert zh[key]["entities"].keys() == en[key]["entities"].keys()
