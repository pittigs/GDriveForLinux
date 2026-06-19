#!/bin/bash
# Get the directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# Add directory to Python path so gdrive_app can be imported correctly
export PYTHONPATH="$DIR:$PYTHONPATH"
# Run the python app
python3 -m gdrive_app.main "$@"
