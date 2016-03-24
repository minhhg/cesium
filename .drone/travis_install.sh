#!/bin/bash

set -ex

section "upgrade.system.supervisor"
sudo pip2.7 install supervisor --upgrade
supervisord --version
section_end "upgrade.system.supervisor"


section "create.virtualenv"
python${TRAVIS_PYTHON_VERSION} -m venv ~/envs/cesium
source ~/envs/cesium/bin/activate
section_end "create.virtualenv"


section "install.base.requirements"
pip install --upgrade pip
hash -d pip  # find upgraded pip
pip install --retries 3 -q requests six python-dateutil nose nose-exclude mock
section_end "install.base.requirements"


section "install.cesium.requirements"
# Python requirements
sed -i 's/>=/==/g' requirements.txt
WHEELHOUSE="--no-index --trusted-host travis-wheels.scikit-image.org \
            --find-links=http://travis-wheels.scikit-image.org/"
WHEELBINARIES="numpy scipy matplotlib scikit-learn pandas pyzmq"
for requirement in $WHEELBINARIES; do
    WHEELS="$WHEELS $(grep $requirement requirements.txt)"
done
pip install --retries 3 -q $WHEELHOUSE $WHEELS
pip install --retries 3 -q -r requirements.txt
pip list
section_end "install.cesium.requirements"


section "build.cython.extensions"
pip install --retries 3 -q $WHEELHOUSE cython==0.23.4
python setup.py build_ext -i
section_end "build.cython.extensions"


section "configure.cesium"
pip install -e .
cesium --install
section_end "configure.cesium"
