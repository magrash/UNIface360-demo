import sys
try:
    import dlib
except Exception as e:
    print('ERROR: cannot import dlib:', e)
    sys.exit(2)

print('dlib version:', dlib.__version__)
print('has cuda attribute:', hasattr(dlib, 'cuda'))
if hasattr(dlib, 'cuda'):
    try:
        num = dlib.cuda.get_num_devices()
        print('dlib.cuda.get_num_devices() ->', num)
    except Exception as e:
        print('dlib.cuda.get_num_devices() raised:', repr(e))
else:
    print('dlib.cuda not present; dlib likely built without CUDA')

try:
    import torch
    print('torch available:', True)
    try:
        print('torch.cuda.is_available():', torch.cuda.is_available())
    except Exception as e:
        print('torch.cuda check failed:', repr(e))
except Exception:
    print('torch not available')

try:
    import face_recognition
    print('face_recognition import OK')
except Exception as e:
    print('face_recognition import failed:', e)
