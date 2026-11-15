# Publishing

For an Errante / NASA Space Apps final demo, follow `errante-demo.md` instead of
the tutorial-description format below. Run `verificar.py <video> --final`, preserve
source/AI credits and metadata, and separately verify the hosted link without login.
The local verifier does not upload or prove anonymous access. Publishing requires
authorization for that action; existing explicit authorization need not be requested again.

1. **Final video.** `montar.py <video>` writes `<publish>/<video>/<video>.mp4` (or `--out` a name the course
   uses). Check it: duration, resolution and fps (`ffmpeg -i`), and a contact sheet.
2. **Description.** `<publish>/<video>/descripcion.md`: what it is about, what you learn (3–4 points, as the
   video does them, not as the docs say), related videos, links. Keep the course's existing format if there is
   one.
3. **A previous version** of the same video is moved out of the publish folder, never deleted: put it in
   `<production>/<video>/version-anterior/` so it is not uploaded again.
4. **Everything that leaves the machine is prepared, not done**: list the files to upload and where, write the
   exact message for whoever publishes (a person, an agent, a platform), draft the announcement. Upload, send
   or post only after the user confirms that specific action. Approval for one action does not extend to the
   next.

Announcement drafts: short, no durations, one line on what the video is, one on what it shows, and the one
practical caveat a viewer needs (a permission, a VPN, a prerequisite). The user sends it.
