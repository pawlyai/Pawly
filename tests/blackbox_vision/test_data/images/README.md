# Vision eval test images

Place the image files for each corpus case in this directory.
The runner (`run_vision_eval.py`) resolves filenames relative to this
directory and skips cases whose files are absent — so a partial image
set is fine.

## Required files

| Filename | Case | What to photograph |
|---|---|---|
| `vis_001_healthy_dog.jpg` | VIS-001 | Healthy, alert dog — clear photo, normal posture |
| `vis_002_wound_limb.jpg` | VIS-002 | Visible cut or abscess on a dog's leg |
| `vis_003_eye_discharge.jpg` | VIS-003 | Cat with discharge in one eye |
| `vis_004_overweight_cat.jpg` | VIS-004 | Noticeably round/overweight cat, relaxed posture |
| `vis_005_houseplant.jpg` | VIS-005 | Houseplant or furniture — no pet in frame |
| `vis_006_blurry.jpg` | VIS-006 | Very blurry, unrecognisable photo |
| `vis_007_lethargic_dog.jpg` | VIS-007 | Dog lying down with laboured breathing or dull eyes |
| `vis_008_skin_rash.jpg` | VIS-008 | Dog belly with redness, bumps or rash |
| `vis_009_food_bowl.jpg` | VIS-009 | Empty food bowl — no pet visible |

VIS-010 has no image (tests text-only fallback) — no file needed.

## Sourcing real images

- Own photos from pet owners on the team work best.
- Public-domain stock images: Unsplash, Pexels, Pixabay (search
  "dog wound", "cat eye", etc.).
- Never use images that identify a real person, or images taken from
  social media without explicit permission.

## Synthetic / placeholder images

For CI runs that do not need the full image corpus, each case has
`"allow_missing_images": true` in the corpus — the runner will skip
the case rather than fail.

To run the full suite without real photos you can use synthetic
solid-colour JPEG stand-ins:

```python
from PIL import Image
Image.new("RGB", (256, 256), color=(200, 200, 200)).save("vis_001_healthy_dog.jpg")
```

Solid-colour images will exercise the upload pipeline and API surface
but will not produce meaningful triage or quality scores.

## Image format requirements

- JPEG or PNG accepted (the iOS client re-encodes to JPEG anyway).
- Max 5 MiB per image (file-service hard cap).
- Minimum 64×64 px; 512×512 px or larger is recommended for the vision
  model to extract meaningful detail.
