from __future__ import annotations

import warnings

from langchain_core._api.deprecation import LangChainPendingDeprecationWarning
from starlette.exceptions import StarletteDeprecationWarning

warnings.filterwarnings("ignore", category=LangChainPendingDeprecationWarning)
warnings.filterwarnings("ignore", category=StarletteDeprecationWarning)
