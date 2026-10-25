FROM maibot-qq-core:1.3.15-memory-fix-edbed3d2a9bd
COPY requirements.txt installed-constraints.txt /tmp/interaction-dependencies/
RUN uv pip install --python /MaiMBot/.venv/bin/python \
    --constraint /tmp/interaction-dependencies/installed-constraints.txt \
    -r /tmp/interaction-dependencies/requirements.txt
