# Geo quiz rollout

Geo quizzes are carousel posts with alternating prompt and answer slides. The default format is three countries per post.

## Format

- Slide 1: country outline or highlighted country, no label.
- Slide 2: same map with the country name, region and one short fact.
- Slide 3: next country prompt.
- Slide 4: next answer.
- Slide 5: next country prompt.
- Slide 6: next answer.

An intro slide is optional. Use it only when the theme needs context, such as "island countries" or "landlocked countries."

## Difficulty

- Easy: familiar outline, large country, common in school maps or news.
- Medium: recognizable outline but less obvious to a general audience.
- Hard: smaller country, similar neighbors or less familiar region.
- Expert: enclaves, microstates, unusual borders or countries often missed on blank maps.

Difficulty should reflect the audience, not geography trivia purity. If the map needs a hint to be fair, lower the difficulty or make it a themed post.

## Batch workflow

1. Pick 10 countries in one difficulty tier.
2. Add them to a batch `quiz.yaml`.
3. Render all prompt and answer slides.
4. Check every prompt slide for accidental hints from labels, neighboring shapes or framing.
5. Check every answer slide for legibility and spelling.
6. Keep a publish log with date, caption and any comments worth turning into a follow-up.

## First country pools

Easy:
- Italy
- Japan
- Australia
- Mexico
- India
- United Kingdom
- Brazil
- South Africa
- Egypt
- Canada

Medium:
- Vietnam
- Chile
- Turkey
- New Zealand
- Greece
- Norway
- Morocco
- Philippines
- Madagascar
- South Korea

Hard:
- Georgia
- Laos
- Uruguay
- Tunisia
- Croatia
- Eritrea
- Kyrgyzstan
- Belize
- Slovenia
- Malawi

Expert:
- Lesotho
- Eswatini
- Brunei
- The Gambia
- Timor-Leste
- Djibouti
- Bhutan
- Suriname
- Comoros
- Sao Tome and Principe

## QA checklist

- Export is `1080x1920`.
- Prompt slide has no answer text.
- Answer slide names the country clearly.
- Map does not crop the highlighted country.
- Disputed borders render as disputed when they appear.
- Source line is present.
- Filename matches the batch and slide order.
