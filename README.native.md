# GoreeCloud Search — Native Development Foundation

This drop-in folder set is intended for `GoreeCloud/search` on a **new feature branch** based on the existing Development branch. It does not replace the current Search runtime, and must not be applied directly to Stable.

Run `python3 -m unittest discover -s tests/native -v` from the repository root. The example corpus contains two **synthetic** entries under `example.org` and does not contact real providers. For usage, boundaries and release gates see `docs/goreecloud/NATIVE-SEARCH-FOUNDATION.md`.

Status: initial native Web-document indexing and explicitly gated crawler only. No broad crawl has been launched, no production service is deployed, and Images/News/Videos native coverage is future work.
