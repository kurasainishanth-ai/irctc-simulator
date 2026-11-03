import sys
with open("test_stdout.txt", "w") as f:
    f.write(str(sys.stdout) + "\n")
    if sys.stdout:
        f.write(str(hasattr(sys.stdout, "buffer")) + "\n")
        f.write(str(getattr(sys.stdout, "encoding", None)) + "\n")
