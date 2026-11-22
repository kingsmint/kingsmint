"""The sample ledger (kingsmint sample), built once for the tests that use it."""
import shutil
from pathlib import Path

import pytest

from kingsmint import importer, sample

TEMPLATE = Path(__file__).parent.parent / "template"


@pytest.fixture(scope="session")
def ledger(tmp_path_factory):
    root = tmp_path_factory.mktemp("sample")
    shutil.copytree(TEMPLATE, root, dirs_exist_ok=True)
    main = root / "main.beancount"
    main.write_text(main.read_text().replace('"TITLE"', '"Sample"').replace("CURRENCY", "EUR")
                    .replace('"LOCALE"', '"sk_SK"').replace('"LANGUAGE_CODE"', '"sk"'))
    with pytest.MonkeyPatch.context() as mp:
        mp.chdir(root)
        mp.setattr(importer, "ROOT", root)
        mp.setattr(importer, "LEDGER", main)
        sample.main()
    return root
