# Avatar Support System - Implementation TODO

- [x] Step 1: Add Avatar model (OneToOne(User) + ImageField) and default fallback behavior

- [x] Step 2: Add AvatarUploadForm with strict validation (size/type/MIME + Pillow image verification)


- [x] Step 3: Add avatar processing service (resize to 256x256 square WebP)

- [x] Step 4: Add profile view + avatar upload/remove routes (CSRF + auth protected)

- [ ] Step 5: Add leaderboard view/template (since none exists today)
- [ ] Step 6: Add reusable template partial: includes/avatar.html
- [ ] Step 7: Integrate avatar rendering into navbar (board.html header) and landing navbar
- [ ] Step 8: Integrate avatar into stats page and match/game panels
- [ ] Step 9: Add CSS styling for avatar (circular, responsive, no layout shift)
- [ ] Step 10: Update Django settings for MEDIA_URL/MEDIA_ROOT (dev-safe) + upload limits
- [ ] Step 11: Update URL config to serve media in development only
- [ ] Step 12: Add migrations
- [ ] Step 13: Add comprehensive tests (upload valid/invalid/size/auth/fallback)
- [ ] Step 14: Update requirements.txt to include Pillow
- [ ] Step 15: Run all tests and flake8
- [ ] Step 16: Final checklist for Vercel safety

