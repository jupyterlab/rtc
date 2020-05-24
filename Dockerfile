# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
ARG BASE_CONTAINER=jupyter/minimal-notebook
FROM $BASE_CONTAINER

LABEL maintainer="Jupyter Project <jupyter@googlegroups.com>"

RUN conda install --quiet --yes yarn && \
    conda update --all --quiet --yes && \
    conda clean --all -f -y && \
    rm -rf /home/$NB_USER/.cache/yarn && \
    fix-permissions $CONDA_DIR && \
    fix-permissions /home/$NB_USER

# Install jupyterlab rtc
COPY ./[^Dockerfile]* /home/$NB_USER/jupyterlab-rtc/
# RUN fix-permissions /home/$NB_USER/jupyterlab-rtc && \
#     cd /home/$NB_USER/jupyterlab-rtc && \
#     yarn run todo:pre && \
#     yarn run todo

# Fix permissions on /etc/jupyter as root
USER root
RUN fix-permissions /etc/jupyter/ && \
    fix-permissions /home/$NB_USER/jupyterlab-rtc/

# Switch back to jovyan to avoid accidental container runs as root
USER $NB_UID
