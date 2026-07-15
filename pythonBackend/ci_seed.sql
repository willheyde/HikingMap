-- ci_seed.sql � small, VARIED fixture data for CI (and local smoke runs).
--
-- Not a copy of production: the point is to span every dimension the
-- integration tests filter on (difficulty, state, length, tags) so a broken
-- filter has rows it must *exclude* � that's what makes the assertions bite.
-- Idempotent: ON CONFLICT DO NOTHING, and all ids use the 5eed�/17e0� ranges
-- so re-running never clobbers real data.

INSERT INTO hikes (id, source_id, name, geometry, difficulty, length_km, elevation_gain_m, min_altitude_m, max_altitude_m, region, state, season_start_month, season_end_month, permits_required, last_synced_at, tags, can_camp, lat, lng) VALUES
  ('5eed0000-0000-4000-8000-000000000000', 'seed-000', 'Cedar Falls Loop', '{"type":"LineString","coordinates":[[-82.75,35.29],[-82.74,35.3]]}', 'EASY', 1.5, 40, 200, 240, 'Pisgah National Forest', 'NC', 1, 12, false, now(), ARRAY['waterfall','forest','loop']::text[], false, 35.29, -82.75),
  ('5eed0000-0000-4000-8000-000000000001', 'seed-001', 'Whitewater Overlook', '{"type":"LineString","coordinates":[[-83.51,35.7],[-83.5,35.71]]}', 'MODERATE', 2.4, 475, 260, 735, 'Great Smoky Mountains', 'TN', 4, 10, false, now(), ARRAY['lake','views','out_and_back']::text[], false, 35.7, -83.51),
  ('5eed0000-0000-4000-8000-000000000002', 'seed-002', 'Sunset Ridge Trail', '{"type":"LineString","coordinates":[[-78.31,38.57],[-78.3,38.58]]}', 'DIFFICULT', 3.3, 910, 320, 1230, 'Shenandoah', 'VA', 4, 10, false, now(), ARRAY['summit','ridge','views']::text[], true, 38.57, -78.31),
  ('5eed0000-0000-4000-8000-000000000003', 'seed-003', 'Meadow Creek Path', '{"type":"LineString","coordinates":[[-82.49,35.66],[-82.47999999999999,35.669999999999995]]}', 'EXPERT', 4.2, 1180, 380, 1560, 'Blue Ridge', 'NC', 6, 9, true, now(), ARRAY['river','wildflowers','meadow']::text[], false, 35.66, -82.49),
  ('5eed0000-0000-4000-8000-000000000004', 'seed-004', 'Balsam Summit', '{"type":"LineString","coordinates":[[-84.02,34.78],[-84.00999999999999,34.79]]}', 'EASY', 5.1, 95, 440, 535, 'Chattahoochee Forest', 'GA', 1, 12, false, now(), ARRAY['forest','loop']::text[], false, 34.78, -84.02),
  ('5eed0000-0000-4000-8000-000000000005', 'seed-005', 'Laurel Gorge', '{"type":"LineString","coordinates":[[-119.59,37.75],[-119.58,37.76]]}', 'MODERATE', 6.0, 530, 200, 730, 'Yosemite', 'CA', 4, 10, false, now(), ARRAY['summit','ridge','exposed']::text[], false, 37.75, -119.59),
  ('5eed0000-0000-4000-8000-000000000006', 'seed-006', 'Hemlock Hollow', '{"type":"LineString","coordinates":[[-82.73,35.31],[-82.72,35.32]]}', 'DIFFICULT', 6.9, 800, 260, 1060, 'Pisgah National Forest', 'NC', 4, 10, false, now(), ARRAY['waterfall','forest','loop']::text[], true, 35.31, -82.73),
  ('5eed0000-0000-4000-8000-000000000007', 'seed-007', 'Panther Ridge', '{"type":"LineString","coordinates":[[-83.49,35.72],[-83.47999999999999,35.73]]}', 'EXPERT', 7.8, 1235, 320, 1555, 'Great Smoky Mountains', 'TN', 6, 9, false, now(), ARRAY['lake','views','out_and_back']::text[], false, 35.72, -83.49),
  ('5eed0000-0000-4000-8000-000000000008', 'seed-008', 'Blue Lake Circuit', '{"type":"LineString","coordinates":[[-78.29,38.59],[-78.28,38.6]]}', 'EASY', 8.7, 150, 380, 530, 'Shenandoah', 'VA', 1, 12, false, now(), ARRAY['summit','ridge','views']::text[], false, 38.59, -78.29),
  ('5eed0000-0000-4000-8000-000000000009', 'seed-009', 'Eagle Rock Scramble', '{"type":"LineString","coordinates":[[-82.47,35.68],[-82.46,35.69]]}', 'MODERATE', 9.6, 420, 440, 860, 'Blue Ridge', 'NC', 4, 10, false, now(), ARRAY['river','wildflowers','meadow']::text[], false, 35.68, -82.47),
  ('5eed0000-0000-4000-8000-00000000000a', 'seed-010', 'Fern Valley Walk', '{"type":"LineString","coordinates":[[-84.1,34.7],[-84.08999999999999,34.71]]}', 'DIFFICULT', 10.5, 855, 200, 1055, 'Chattahoochee Forest', 'GA', 4, 10, false, now(), ARRAY['forest','loop']::text[], true, 34.7, -84.1),
  ('5eed0000-0000-4000-8000-00000000000b', 'seed-011', 'Granite Dome Route', '{"type":"LineString","coordinates":[[-119.57,37.77],[-119.55999999999999,37.78]]}', 'EXPERT', 11.4, 1290, 260, 1550, 'Yosemite', 'CA', 6, 9, false, now(), ARRAY['summit','ridge','exposed']::text[], false, 37.77, -119.57),
  ('5eed0000-0000-4000-8000-00000000000c', 'seed-012', 'Mossy Rock Trail', '{"type":"LineString","coordinates":[[-82.71,35.33],[-82.69999999999999,35.339999999999996]]}', 'EASY', 12.3, 40, 320, 360, 'Pisgah National Forest', 'NC', 1, 12, false, now(), ARRAY['waterfall','forest','loop']::text[], false, 35.33, -82.71),
  ('5eed0000-0000-4000-8000-00000000000d', 'seed-013', 'Iron Mountain Way', '{"type":"LineString","coordinates":[[-83.47,35.74],[-83.46,35.75]]}', 'MODERATE', 13.2, 475, 380, 855, 'Great Smoky Mountains', 'TN', 4, 10, false, now(), ARRAY['lake','views','out_and_back']::text[], false, 35.74, -83.47),
  ('5eed0000-0000-4000-8000-00000000000e', 'seed-014', 'Willow Bend Loop', '{"type":"LineString","coordinates":[[-78.27,38.61],[-78.25999999999999,38.62]]}', 'DIFFICULT', 14.1, 910, 440, 1350, 'Shenandoah', 'VA', 4, 10, false, now(), ARRAY['summit','ridge','views']::text[], true, 38.61, -78.27),
  ('5eed0000-0000-4000-8000-00000000000f', 'seed-015', 'Thunderhead Climb', '{"type":"LineString","coordinates":[[-82.55,35.6],[-82.53999999999999,35.61]]}', 'EXPERT', 15.0, 1180, 200, 1380, 'Blue Ridge', 'NC', 6, 9, true, now(), ARRAY['river','wildflowers','meadow']::text[], false, 35.6, -82.55),
  ('5eed0000-0000-4000-8000-000000000010', 'seed-016', 'Pinecrest Amble', '{"type":"LineString","coordinates":[[-84.08,34.72],[-84.07,34.73]]}', 'EASY', 15.9, 95, 260, 355, 'Chattahoochee Forest', 'GA', 1, 12, false, now(), ARRAY['forest','loop']::text[], false, 34.72, -84.08),
  ('5eed0000-0000-4000-8000-000000000011', 'seed-017', 'Raven Cliff Ascent', '{"type":"LineString","coordinates":[[-119.55,37.79],[-119.53999999999999,37.8]]}', 'MODERATE', 16.8, 530, 320, 850, 'Yosemite', 'CA', 4, 10, false, now(), ARRAY['summit','ridge','exposed']::text[], false, 37.79, -119.55),
  ('5eed0000-0000-4000-8000-000000000012', 'seed-018', 'Silver Brook Trail', '{"type":"LineString","coordinates":[[-82.69,35.35],[-82.67999999999999,35.36]]}', 'DIFFICULT', 17.7, 800, 380, 1180, 'Pisgah National Forest', 'NC', 4, 10, false, now(), ARRAY['waterfall','forest','loop']::text[], true, 35.35, -82.69),
  ('5eed0000-0000-4000-8000-000000000013', 'seed-019', 'Bald Knob Traverse', '{"type":"LineString","coordinates":[[-83.45,35.76],[-83.44,35.769999999999996]]}', 'EXPERT', 18.6, 1235, 440, 1675, 'Great Smoky Mountains', 'TN', 6, 9, false, now(), ARRAY['lake','views','out_and_back']::text[], false, 35.76, -83.45),
  ('5eed0000-0000-4000-8000-000000000014', 'seed-020', 'Otter Pond Loop', '{"type":"LineString","coordinates":[[-78.35,38.53],[-78.33999999999999,38.54]]}', 'EASY', 19.5, 150, 200, 350, 'Shenandoah', 'VA', 1, 12, false, now(), ARRAY['summit','ridge','views']::text[], false, 38.53, -78.35),
  ('5eed0000-0000-4000-8000-000000000015', 'seed-021', 'Storm Peak Route', '{"type":"LineString","coordinates":[[-82.53,35.62],[-82.52,35.629999999999995]]}', 'MODERATE', 20.4, 420, 260, 680, 'Blue Ridge', 'NC', 4, 10, false, now(), ARRAY['river','wildflowers','meadow']::text[], false, 35.62, -82.53),
  ('5eed0000-0000-4000-8000-000000000016', 'seed-022', 'Aspen Meadow Trail', '{"type":"LineString","coordinates":[[-84.06,34.74],[-84.05,34.75]]}', 'DIFFICULT', 21.3, 855, 320, 1175, 'Chattahoochee Forest', 'GA', 4, 10, false, now(), ARRAY['forest','loop']::text[], true, 34.74, -84.06),
  ('5eed0000-0000-4000-8000-000000000017', 'seed-023', 'Devils Staircase', '{"type":"LineString","coordinates":[[-119.53,37.81],[-119.52,37.82]]}', 'EXPERT', 22.2, 1290, 380, 1670, 'Yosemite', 'CA', 6, 9, false, now(), ARRAY['summit','ridge','exposed']::text[], false, 37.81, -119.53)
ON CONFLICT (id) DO NOTHING;

-- A seeded ADMIN account so the integration suite can exercise the admin-gated
-- hike write routes (create/update/delete). Password is 'ci-admin-pw-12345'
-- (bcrypt hash below). CI-only fixture — never a real credential.
INSERT INTO users (id, email, hashed_password, name, created_at, auth_provider, is_admin) VALUES
  ('ad310000-0000-4000-8000-000000000001', 'ci-admin@example.com',
   '$2b$12$aE2bHZrI3qWj00eLrZ6gL.zf.WgOV7vLpm7UrzRK3ugG/wKJcAXWi',
   'CI Admin', now(), 'password', true)
ON CONFLICT (id) DO NOTHING;

INSERT INTO items (id, name, weight, cost, item_type, attributes) VALUES
  ('17e00000-0000-4000-8000-000000000000', 'Trailhead 55L Pack', 1300, 189, 'backpack', '{"capacity_liters": 55, "frame_type": "internal"}'::jsonb),
  ('17e00000-0000-4000-8000-000000000001', 'Summit 2P Tent', 1900, 349, 'shelter', '{"capacity_persons": 2, "season_rating": "3_season", "shelter_type": "tent"}'::jsonb),
  ('17e00000-0000-4000-8000-000000000002', 'Ridgeline Boots', 820, 165, 'footwear', '{"waterproof": true, "ankle_support": "mid"}'::jsonb),
  ('17e00000-0000-4000-8000-000000000003', 'Ember 20F Bag', 1100, 220, 'sleeping_bag', '{"temp_rating_f": 20, "fill_type": "down"}'::jsonb),
  ('17e00000-0000-4000-8000-000000000004', 'Flowstate Filter', 110, 45, 'water', '{"system_type": "filter", "flow_rate_lpm": 1.5}'::jsonb),
  ('17e00000-0000-4000-8000-000000000005', 'Beacon Headlamp', 95, 40, 'lighting', '{"lumens": 400, "lighting_type": "headlamp"}'::jsonb)
ON CONFLICT (id) DO NOTHING;

