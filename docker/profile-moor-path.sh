# shellcheck shell=sh
# Installed as /etc/profile.d/moor.sh. Debian's /etc/profile resets PATH for
# every login shell (`bash -l`, `docker exec <c> bash -l`, ssh, the terminal
# tool's background `bash -lic`), dropping the image's ENV PATH dirs, so bare
# `moor` exits 127 there. Put them back in the ENV PATH order; dirs a login
# PATH already lists keep their position.
for __moor_p in /opt/data/.local/bin /opt/moor/.venv/bin /opt/moor/bin; do
    case ":$PATH:" in
        *":$__moor_p:"*) ;;
        *) PATH="$__moor_p:$PATH" ;;
    esac
done
unset __moor_p
export PATH
