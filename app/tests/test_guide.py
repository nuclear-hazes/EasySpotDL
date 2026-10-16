from easyspotdl import config

GUIDE = config.ROOT_DIR / "docs" / "user" / "LEEME.txt"


def test_guide_has_required_sections():
    lines = [line.strip() for line in GUIDE.read_text(encoding="utf-8").splitlines()]
    for section in ["Mac", "Windows", "Dónde quedan los MP3", "Si algo falla"]:
        assert section in lines, f"missing section {section!r}"
