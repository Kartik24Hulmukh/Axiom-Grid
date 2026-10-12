<#
.SYNOPSIS
    Fail-closed notice for the unverified Windows installation path.
.DESCRIPTION
    No remote bootstrap, cloning, model pull, machine changes or app launch.
    Read docs/LOCAL_INSTALL.md in a reviewed local checkout.
    Windows clean-host/native installation and signed artifacts are NOT verified.
    The Linux developer workflows remain available through install.sh/install.py.
#>
$ErrorActionPreference = "Stop"
Write-Error "Automated Windows installation is blocked: no verified installer or clean-host evidence. Review docs/LOCAL_INSTALL.md; no changes were made." -ErrorAction Continue
exit 1
