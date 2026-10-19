set -euo pipefail
cd "$(dirname "$0")"
if [ -f .env ]; then set -a; . ./.env; set +a; fi
CMD="${1:-up}"

[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -r task1_brain/requirements.txt -r task3_scope/requirements.txt
[ -d task2_inbox/node_modules ] || (cd task2_inbox && npm install --silent)

need_key() { : "${ANTHROPIC_API_KEY:?Put your key in .env (copy .env.example)}"; }

case "$CMD" in
  test)
    (cd task1_brain && python -m pytest -q)
    (cd task3_scope && python -m pytest -q)
    (cd task2_inbox && npm run -s typecheck && npm test --silent)
    ;;
  crawl)   # first full read of the help center (resumable: just run it again if it stops)
    need_key; (cd task1_brain && python -m app.cli crawl)
    ;;
  eval)
    need_key
    (cd task1_brain && python -m evals.run_evals)
    (cd task2_inbox && npm run -s eval && npm run -s simulate)
    (cd task3_scope && python -m evals.run_evals)
    ;;
  up)
    need_key
    trap 'kill 0' EXIT INT TERM
    (cd task1_brain && uvicorn app.main:app --port 8001) &
    sleep 2
    (cd task3_scope && BRAIN_URL=http://localhost:8001 uvicorn app.main:app --port 8003) &
    (cd task2_inbox && BRAIN_URL=http://localhost:8001 npm start --silent) &
    echo; echo "Task 1 Knowledge Brain : http://localhost:8001   (API docs: /docs)"
    echo "Task 2 Inbox Agent     : http://localhost:3002"
    echo "Task 3 Scope of Work   : http://localhost:8003"; echo
    wait
    ;;
  *) echo "usage: ./run.sh [up|crawl|test|eval]"; exit 1;;
esac
