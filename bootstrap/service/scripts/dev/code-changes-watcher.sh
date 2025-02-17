#!/bin/bash
inotifywait --recursive --monitor --exclude "^${WORKDIR}/logs" --format "%e %w%f" \
    --event modify,move,create,delete ${WORKDIR} |
    while read changed; do
        processes=('process-tasks-general' 'process-tasks-scrape' 'process-tasks-pre-staging' 'process-tasks-post-staging')

        for proc in ${processes[@]}; do
            echo "Starting ${proc}..."
            supervisorctl restart "${proc}" || true
        done

    done
