# HikeBuilder test run — 2026-07-04T05:03:46.755840+00:00

## Test 1: Waterfall hike in NC

**Still needs human judgment:**
- Narrative picks correctly carry the waterfall tag

**Automated checks:**

**Turn 1 — user:** Waterfall hike in NC

> No matching trails were found near this destination that fit your criteria. It seems we couldn't find any moderate difficulty trails with a waterfall feature. Would you like to try adjusting the difficulty level, such as looking for easier trails, or changing the trip length to see if that yields more options?

_phase: destination_

---

## Test 2: Great views near Raleigh

**Still needs human judgment:**
- Cross-checked against other tests for distance-away consistency (see report footer)

**Automated checks:**
- FAIL: numbering: numbering NOT sequential: [1, 2, 3, 1, 2, 3, 4, 5]

**Turn 1 — user:** Great views near Raleigh

> You're looking for hikes with great views near Raleigh. Considering your gear, I notice you have a GPS device and water purification tablets, but you may want to consider additional items for a comfortable hike. 
> 
> My top three picks are: 
> 1. Regency Creek Trail, which offers a flat and short hike with a viewpoint and waterfall.
> 2. Sludge, which has a gentle gain and historic features along with a viewpoint and waterfall.
> 3. 286 Outer Trail, which also has a gentle gain and historic features, and includes a pier and viewpoint.
> 
> Here are the 5 hike options:
> 1. Regency Creek Trail (ID: b9db7a24-b0f8-4b66-b05e-5b8913439daa): 2.25 km, Easy, Gain: 81.0 m, 14 km away, Nc, Tags: [flat, lake, lowland, overpass_enriched, picnic, river, shelter, short, viewpoint, waterfall, wildlife, year_round]
>    Gear check: missing: illumination, first aid | worth noting: insulation, footwear
> 2. Sludge (ID: aa2a6d8a-33bc-40a2-b807-64bd385153d3): 3.51 km, Easy, Gain: 153.0 m, 15 km away, Nc, Tags: [gentle_gain, historic, lake, lowland, overpass_enriched, river, shelter, short, viewpoint, waterfall, wildlife, year_round]
>    Gear check: missing: illumination, first aid | worth noting: insulation, footwear
> 3. 286 Outer Trail (ID: ae076264-c0db-42d8-9b46-196e8cc5aee1): 4.26 km, Easy, Gain: 143.0 m, 17 km away, Nc, Tags: [gentle_gain, historic, lake, lowland, overpass_enriched, pier, river, shelter, short, viewpoint, waterfall, year_round]
>    Gear check: missing: illumination, first aid | worth noting: insulation, footwear
> 4. Loop 1 (ID: 4e5be90d-240f-4cd8-9903-eee9cf89c639): 2.94 km, Easy, Gain: 75.0 m, 18 km away, Nc, Tags: [beach, flat, historic, lake, lowland, overpass_enriched, pier, river, shelter, short, viewpoint, waterfall, wetland, year_round]
>    Gear check: missing: illumination, first aid | worth noting: insulation, footwear
> 5. Loop 4 (ID: 48f47e83-a243-47e5-bbb2-8f8c36947212): 2.29 km, Easy, Gain: 85.0 m, 18 km away, Nc, Tags: [beach, flat, historic, lake, lowland, overpass_enriched, pier, river, shelter, short, viewpoint, waterfall
> 
> Which one would you like? Just give me the number.

_phase: destination_

---

## Test 3: Summit hike, then location

**Still needs human judgment:**
- Clarifies location/difficulty/days before answering
- Tags include summit

**Automated checks:**

**Turn 1 — user:** Summit hike

> You're looking for a summit hike. To help narrow down some options, can you tell me approximately how many days you'd like the hike to be and what difficulty level you're comfortable with? Additionally, do you have a specific region or location in mind for this summit hike?

_phase: destination_

**Turn 2 — user:** In NC

> No matching trails were found near this destination in North Carolina. It seems we have a data gap for trails in this area, especially for summit hikes. Would you like to try a different area in North Carolina, adjust the difficulty level, or change the trip length to see if we can find a suitable option?

_phase: destination_

---

## Test 4: Easy ridge hike, 1-2 miles, then location

**Still needs human judgment:**
- Numbering is sequential, not all '1.'

**Automated checks:**

**Turn 1 — user:** Easy ridge hike, 1-2 miles

> For a short and easy ridge hike, I'd love to know where you'd like to go. Are you looking to stay close to home or explore a new area? Additionally, are you leaning towards a 1-mile hike or would you be open to something up to 2 miles?

_phase: destination_

**Turn 2 — user:** In NC

> No trails were found near your destination in NC that match your criteria. If you'd like to try a different area, adjust the difficulty level, or change the trip length, I can try to help you find a suitable hike. Alternatively, we could explore other options in NC, such as looking for trails with similar features or adjusting the distance to find a better fit.

_phase: destination_

---

## Test 5: Easy lake hike in NC

**Still needs human judgment:**
- Tags match narrative claims (flat/beach/lake/picnic)

**Automated checks:**

**Turn 1 — user:** Easy lake hike in NC

> No matching trails were found near this destination that fit your criteria of an easy lake hike in NC. If you'd like to try a different area, adjust the difficulty level, or change the trip length, I can help you explore other options.

_phase: destination_

---

## Test 6: Easy flat hike, nothing strenuous

**Still needs human judgment:**
- Negated-difficulty phrasing still resolves to Easy

**Automated checks:**

**Turn 1 — user:** Easy flat hike, nothing strenuous

> For an easy, flat hike, I'll look for options that fit your criteria. To narrow down the search, can you tell me where you'd like to go? Are you open to suggestions or do you have a specific region in mind? Additionally, how many days are you planning for this hike?

_phase: destination_

---

## Test 7: Challenging hike -> near me -> NC

**Still needs human judgment:**
- Honest disclosure when no high_gain trails exist
- Offers closest alternatives

**Automated checks:**
- FAIL: expected a DATA NOTE but none was found

**Turn 1 — user:** Challenging hike, major elevation gain

> You're looking for a challenging hike with significant elevation gain. That sounds exciting. To help narrow down some options, can you tell me how many days you're planning for this hike and what general region or location you're interested in? This will help me provide more tailored suggestions for you.

_phase: destination_

**Turn 2 — user:** Near me

> No matching trails were found near your current destination that fit your criteria for a hard hike. It's possible that there may be trails with moderate or easy difficulty that could still offer a great experience. Would you like to try looking at moderate or easy trails instead, or adjust your search to a different area or trip length?

_phase: destination_

**Turn 3 — user:** In NC

> No trails were found in NC that match your current criteria. It seems there's a gap in the data for trails with the specific features you're looking for in this area. Would you like to try adjusting the difficulty level, looking for trails with different features, or exploring a different part of North Carolina?

_phase: destination_

---

## Test 8: Short hike 2hr max -> Charlotte -> NC -> Easy

**Still needs human judgment:**
- Honest 'no trails' in Charlotte
- Broadens correctly on request

**Automated checks:**
- FAIL: numbering: numbering NOT sequential: [1, 2, 3, 1, 1, 1, 1, 1]

**Turn 1 — user:** Short hike, 2 hours max

> You're looking for a short hike that can be completed within 2 hours. That's a great way to get some exercise and enjoy the outdoors. 
> 
> To help narrow down some options, can you tell me what region or location you're interested in hiking in? Are you open to any type of terrain or difficulty level, or are you looking for something relatively easy?

_phase: destination_

**Turn 2 — user:** Charlotte

> You're looking for a short hike in the Charlotte area that can be completed within 2 hours. 
> 
> My top three picks are: 
> 1. Tower Trail, a short and moderate hike with a great viewpoint.
> 2. Crowders Trail, a moderate hike with a variety of features like a lake and waterfall.
> 3. Blue Trail, a moderate hike with a gentle gain and scenic views of a lake.
> 
> Here are the hike options:
> 1. Tower Trail (ID: e72917a4-3098-4961-88f9-db10fc1b67a1): 1.84 miles, Moderate, Gain: 961 ft, 40 km away, Nc, Tags: [cliff, gentle_gain, lake, lowland, overpass_enriched, river, short, summit, viewpoint, year_round]
>    Gear check: missing: illumination, first aid | worth noting: insulation, rain gear, footwear
> 2. Crowders Trail (ID: 6f110dbe-07cc-43fd-8185-31d81c87587f): 2.52 miles, Moderate, Gain: 548 ft, 40 km away, Nc, camping available, Tags: [cliff, gentle_gain, lake, lowland, overpass_enriched, pier, river, short, summit, viewpoint, waterfall, wetland, year_round]
>    Gear check: missing: illumination, first aid, shelter, sleep system | worth noting: insulation, rain gear, footwear
> 3. Lake Shore Trail (ID: 09c293f6-8eba-4156-a145-7f7e721899b3): 2.73 miles, Moderate, Gain: 600 ft, 49 km away, Nc, camping available, Tags: [beach, gentle_gain, lowland, overpass_enriched, pier, river, shelter, short, swimming, year_round]
>    Gear check: missing: illumination, first aid, shelter, sleep system | worth noting: insulation, rain gear, footwear
> 4. Blue Trail (ID: e0e63378-31bf-45ef-9723-7b690ce93eea): 2.55 miles, Moderate, Gain: 597 ft, 61 km away, Nc, Tags: [gentle_gain, lake, lowland, overpass_enriched, river, short, year_round]
>    Gear check: missing: illumination, first aid | worth noting: insulation, rain gear, footwear
> 5. Sugarloaf Mountain Trail (ID: c1dd1be3-2650-4111-ab20-bf6473ce2f4b): 3.02 miles, Moderate, Gain: 779 ft, 70 km away, Nc, camping available, Tags: [gentle_gain, historic, lake, lowland, overpass_enriched, river, shelter, short, summit, viewpoint, wetland, year_round]
>    Gear check: missing: illumination, first aid, shelter, sleep system | worth noting: insulation, rain gear, footwear
> 
> Please pick a hike by
> 
> Which one would you like? Just give me the number.

_phase: destination_

**Turn 3 — user:** NC

> You're looking for a short hike in North Carolina that can be completed within 2 hours. 
> 
> My top three picks are: 
> 1. Tower Trail, a short and moderate hike with a great viewpoint.
> 2. Crowders Trail, a moderate hike with a variety of features like a lake and waterfall.
> 3. Blue Trail, a moderate hike with a gentle gain and scenic views of a lake.
> 
> Here are the hike options:
> 1. **Tower Trail (ID**: e72917a4-3098-4961-88f9-db10fc1b67a1): 1.84 miles, Moderate, Gain: 961 ft, 40 km away, Nc, Tags: [cliff, gentle_gain, lake, lowland, overpass_enriched, river, short, summit, viewpoint, year_round]
>    Gear check: missing: illumination, first aid | worth noting: insulation, rain gear, footwear
> 1. **Crowders Trail (ID**: 6f110dbe-07cc-43fd-8185-31d81c87587f): 2.52 miles, Moderate, Gain: 548 ft, 40 km away, Nc, camping available, Tags: [cliff, gentle_gain, lake, lowland, overpass_enriched, pier, river, short, summit, viewpoint, waterfall, wetland, year_round]
>    Gear check: missing: illumination, first aid, shelter, sleep system | worth noting: insulation, rain gear, footwear
> 1. **Lake Shore Trail (ID**: 09c293f6-8eba-4156-a145-7f7e721899b3): 2.73 miles, Moderate, Gain: 600 ft, 49 km away, Nc, camping available, Tags: [beach, gentle_gain, lowland, overpass_enriched, pier, river, shelter, short, swimming, year_round]
>    Gear check: missing: illumination, first aid, shelter, sleep system | worth noting: insulation, rain gear, footwear
> 1. **Blue Trail (ID**: e0e63378-31bf-45ef-9723-7b690ce93eea): 2.55 miles, Moderate, Gain: 597 ft, 61 km away, Nc, Tags: [gentle_gain, lake, lowland, overpass_enriched, river, short, year_round]
>    Gear check: missing: illumination, first aid | worth noting: insulation, rain gear, footwear
> 1. **Sugarloaf Mountain Trail (ID**: c1dd1be3-2650-4111-ab20-bf6473ce2f4b): 3.02 miles, Moderate, Gain: 779 ft, 70 km away, Nc, camping available, Tags: [gentle_gain, historic, lake, lowland, overpass_enriched, river, shelter, short, summit, viewpoint, wetland, year_round]
>    Gear check: missing: illumination, first aid, shelter, sleep system | worth noting: insulation, rain gear, footwear
> 
> Please
> 
> Which one would you like? Just give me the number.

_phase: destination_

**Turn 4 — user:** Easy

> You're looking for an easy, short hike in North Carolina that can be completed within 2 hours. 
> 
> My top three picks are: 
> 1. Tower Trail, a short and moderate hike with a great viewpoint, though it may be a bit more challenging than easy.
> 2. Blue Trail, a moderate hike with a gentle gain and scenic views of a lake.
> 3. Lake Shore Trail, a moderate hike with a gentle gain and scenic views of a lake and beach.
> 
> Here are the hike options:
> 1. **Tower Trail (ID**: e72917a4-3098-4961-88f9-db10fc1b67a1): 1.84 miles, Moderate, Gain: 961 ft, 40 km away, Nc, Tags: [cliff, gentle_gain, lake, lowland, overpass_enriched, river, short, summit, viewpoint, year_round]
>    Gear check: missing: illumination, first aid | worth noting: insulation, rain gear, footwear
> 1. **Crowders Trail (ID**: 6f110dbe-07cc-43fd-8185-31d81c87587f): 2.52 miles, Moderate, Gain: 548 ft, 40 km away, Nc, camping available, Tags: [cliff, gentle_gain, lake, lowland, overpass_enriched, pier, river, short, summit, viewpoint, waterfall, wetland, year_round]
>    Gear check: missing: illumination, first aid, shelter, sleep system | worth noting: insulation, rain gear, footwear
> 1. **Lake Shore Trail (ID**: 09c293f6-8eba-4156-a145-7f7e721899b3): 2.73 miles, Moderate, Gain: 600 ft, 49 km away, Nc, camping available, Tags: [beach, gentle_gain, lowland, overpass_enriched, pier, river, shelter, short, swimming, year_round]
>    Gear check: missing: illumination, first aid, shelter, sleep system | worth noting: insulation, rain gear, footwear
> 1. **Blue Trail (ID**: e0e63378-31bf-45ef-9723-7b690ce93eea): 2.55 miles, Moderate, Gain: 597 ft, 61 km away, Nc, Tags: [gentle_gain, lake, lowland, overpass_enriched, river, short, year_round]
>    Gear check: missing: illumination, first aid | worth noting: insulation, rain gear, footwear
> 1. **Sugarloaf Mountain Trail (ID**: c1dd1be3-2650-4111-ab20-bf6473ce2f4b): 3.02 miles, Moderate, Gain: 779 ft, 70 km away, Nc, camping available, Tags: [gentle_gain, historic, lake, lowland, overpass_enriched, river, shelter, short, summit, viewpoint, wetland, year_round]
>    Gear check: missing: illumination, first aid, shelter
> 
> Which one would you like? Just give me the number.

_phase: destination_

---

## Test 9: Historic trails or ruins (multi-turn path)

**Still needs human judgment:**
- Every result has a real ID — no hallucinated non-DB trail names

**Automated checks:**
- PASS: every numbered listing had real IDs attached

**Turn 1 — user:** Historic trails or ruins

> Let's explore some historic trails or ruins for your hiking trip. To narrow down the options, can you tell me how many days you'd like to spend on the trail and what level of difficulty you're comfortable with? Are you looking for an easy, moderate, or challenging hike? Additionally, is there a specific region or location you're interested in, such as the Southwest or the East Coast?

_phase: destination_

**Turn 2 — user:** I haven't decided on difficulty yet

> We can keep the difficulty level open for now. To help find a good fit, can you tell me how many days you'd like to spend on the trail? Are you looking for a short 2-3 day trip or a longer 5-7 day adventure? Also, is there a specific region or location you're interested in, such as the Southwest, the East Coast, or somewhere else?

_phase: destination_

**Turn 3 — user:** Just a day hike

> A day hike to explore historic trails or ruins sounds like a great idea. Since you're looking for a day hike, we can focus on finding a trail that's approx. 5-10 miles round trip. Are you open to hiking in any state or region, or do you have a specific area in mind, such as Arizona, New Mexico, or the Northeast?

_phase: destination_

**Turn 4 — user:** ok im waiting

> I'm waiting for more information to provide you with some hike options. To confirm, you're looking for a day hike to explore historic trails or ruins, with an approx. 5-10 mile round trip distance. You're open to hiking in any state or region. Once I have a better understanding of your preferences, I can provide you with some hike options.

_phase: destination_

---

## Test 10: Meadows and wildflowers

**Still needs human judgment:**
- Results tagged meadow

**Automated checks:**
- FAIL: expected a DATA NOTE but none was found

**Turn 1 — user:** Meadows and wildflowers in NC

> No matching trails were found near this destination that fit your criteria of meadows and wildflowers in NC, especially considering you're looking for an easy hike. Would you like to try a different area in NC, adjust the difficulty level, or change the trip length to see if other options are available?

_phase: destination_

---

## Cross-test distance-away consistency

No inconsistencies found.
