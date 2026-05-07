---
model: gemini-3.1-flash-image-preview
aspect_ratio: "4:3"
---

# Image generation context — *Firefighter Ruaridh*

Use with Gemini in one chat session so art style stays consistent across all images.

## Session seed (paste first)

> I am creating illustrations for a **children's picture book** for home print. For every image in this chat, follow these constraints closely.
>
> **Art style:** Bright, warm watercolour and coloured pencil. Rounded, friendly shapes. Slightly textured paper feel. The garden setting should feel cosy and safe — late afternoon golden light, lush green grass, flower beds. The campfire scene (spread 5 and 6) should have warm amber and orange glow against a soft dusky sky.
>
> **Aspect ratio:** **4:3** landscape — keep this the same for all images.
>
> **Tone:** Playful, proud, warm. This is a toddler's dress-up adventure. The garden is entirely safe and familiar — no danger, just imagination and joy.
>
> **Characters (keep consistent across all images):**
>
> - **Ruaridh:** A toddler boy, nearly three. Short, slightly wavy dark-blond hair. Large blue eyes, round rosy cheeks. Wearing a child-sized red plastic firefighter helmet that is slightly too big, a small yellow hi-vis tabard (over everyday clothes), and yellow wellington boots. He carries or holds a coiled green garden hose. Proud, determined expression. Keep him recognisably the **same child** in every illustration.
> - **Finlay:** A tiny baby (2 months old). Fine wispy dark-brown hair, large round blue-grey eyes, very full cheeks. Dressed in a soft onesie. Always sitting in a blue pram/pushchair when outdoors. Happy, wide-eyed, occasionally babbling.
> - **Max:** A **black and white spaniel** — predominantly white with black ticking (small spots and roaning) across the body, solid black long floppy ears, and a clear white blaze running down the centre of his face. Energetic and curious. Never anthropomorphised — he can sniff, wag, or bark but does not speak or wear clothes.
> - **Mum (Beth):** A woman with shoulder-length naturally wavy medium-brown hair, a round face with soft features, blue eyes, and naturally rosy cheeks. Warm, smiling expression.
> - **Dad (Paddy):** A man with short light sandy-brown hair, blue eyes, and a neatly trimmed ginger-brown goatee and moustache. Enthusiastic, outdoorsy manner.
>
> **The garden:** A typical British family back garden. Green lawn, flower beds along the fence, an apple tree, a rose bush, a large mature tree at the back. Wooden fence panels. A garden tap on the side of the house with an orange or green hose attached.
>
> **The campfire (spreads 5 and 6):** A small, cheerful campfire in a simple metal fire bowl or ring of stones on the lawn. Warm orange and amber flames. Safe and cosy, never threatening. Five long roasting sticks with marshmallows visible in spread 6.
>
> Acknowledge these rules. I will paste scene prompts next.

## Continuity notes

- Ruaridh's red helmet is **slightly too big** — it sits a little low on his forehead. This is deliberate; keep it in every image.
- Max's tail is wagging in every garden scene.
- Finlay's pram is always the same blue pushchair.
- In spreads 1–4 it is **bright afternoon**. In spreads 5–6 the sky has shifted to **warm dusk / early evening** — soft orangey-pink on the horizon, still light enough to see clearly.

## Files in this folder

- `cover-image.md` — book cover
- `spread-1-image.md` … `spread-6-image.md` — scene prompts for automation (`scripts/generate_images.py`) or manual paste into Gemini.
