"""
TLS trust for the PRP API.

prp.parliament.gov.bd serves only its leaf certificate and omits the
`GoGetSSL RSA DV CA` intermediate. Browsers fetch the missing intermediate on
the fly (AIA), but `requests`/`certifi` do not, so verification fails with
"unable to get local issuer certificate". We build a CA bundle that is
certifi's normal roots PLUS the bundled intermediate, letting the chain resolve
to the USERTrust root without disabling verification.
"""
import functools
import os
import tempfile

import certifi

_INTERMEDIATE = os.path.join(os.path.dirname(__file__), "certs", "prp_chain.pem")


@functools.lru_cache(maxsize=1)
def ca_bundle() -> str:
    """
    Path to a PEM bundle = certifi roots + the PRP intermediate.

    Written once to a temp file and cached for the process lifetime. Pass the
    result as `verify=` to every requests call against the PRP API.
    """
    with open(certifi.where(), "rb") as f:
        data = f.read()
    with open(_INTERMEDIATE, "rb") as f:
        data += b"\n" + f.read()

    bundle_path = os.path.join(tempfile.gettempdir(), "prp_ca_bundle.pem")
    with open(bundle_path, "wb") as f:
        f.write(data)
    return bundle_path
