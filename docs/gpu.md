# GPU mode

uild.py render --gpu (and python -m world_execute_replica render --gpu) switches
bloom, trail and scanlines to a GPU implementation.

Requires a Python with torch + CUDA (pass it with --python), otherwise the
CPU path is used. Set DSH_GPU=1 in the environment to force the GPU branch.
