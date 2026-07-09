-- schema.sql — full from-scratch schema for the HikeBuilder database.
--
-- Generated with `pg_dump --schema-only --no-owner --no-privileges`. This is the
-- one artifact that lets a brand-new empty Postgres be brought up to the current
-- structure in a single step (the migrations/ files only *alter* these tables;
-- they don't create the core ones). CI applies this to a fresh DB before booting
-- the app. Regenerate it after a schema change so it stays authoritative.
--
--   psql -h <host> -U <user> -d <db> -f schema.sql
--
-- PostgreSQL database dump
--

-- Dumped from database version 17.5
-- Dumped by pg_dump version 17.5

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: hike_completions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hike_completions (
    trip_id uuid NOT NULL,
    went boolean NOT NULL,
    difficulty_felt character varying,
    elevation_felt text,
    rating integer,
    notes text,
    reviewed_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT hike_completions_rating_check CHECK (((rating IS NULL) OR ((rating >= 1) AND (rating <= 5))))
);


--
-- Name: hike_gear_requirements; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hike_gear_requirements (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    hike_id uuid NOT NULL,
    gear_tag text NOT NULL,
    importance text DEFAULT 'required'::text NOT NULL,
    CONSTRAINT hike_gear_requirements_importance_check CHECK ((importance = ANY (ARRAY['required'::text, 'recommended'::text, 'optional'::text])))
);


--
-- Name: hikes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hikes (
    id uuid NOT NULL,
    source_id character varying,
    name character varying NOT NULL,
    geometry text NOT NULL,
    difficulty character varying,
    length_km double precision,
    elevation_gain_m double precision,
    min_altitude_m double precision,
    max_altitude_m double precision,
    region character varying,
    season_start_month integer,
    season_end_month integer,
    permits_required boolean,
    nearest_airport_code character varying,
    parking_coordinates text,
    last_synced_at timestamp without time zone,
    tags text[] DEFAULT '{}'::text[] NOT NULL,
    can_camp boolean DEFAULT false NOT NULL,
    lat double precision,
    lng double precision,
    state character varying(50),
    gear_requirements jsonb DEFAULT '{}'::jsonb NOT NULL,
    trail_shape text
);


--
-- Name: items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.items (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying NOT NULL,
    weight double precision,
    cost double precision,
    item_type character varying NOT NULL,
    image_url character varying,
    attributes jsonb DEFAULT '{}'::jsonb NOT NULL
);


--
-- Name: schema_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.schema_migrations (
    version text NOT NULL,
    applied_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: trip_gear; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.trip_gear (
    trip_id uuid NOT NULL,
    item_id uuid NOT NULL,
    status text DEFAULT 'owned'::text
);


--
-- Name: trip_stops; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.trip_stops (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    trip_id uuid,
    stop_order integer NOT NULL,
    destination text NOT NULL,
    lat double precision,
    lng double precision,
    duration_days integer,
    activity_type text,
    itinerary jsonb,
    trail_data jsonb,
    camping jsonb,
    cost_estimate jsonb,
    travel_from_prev jsonb,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: trips; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.trips (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid,
    created_at timestamp without time zone,
    title text,
    goal text,
    status character varying(20) DEFAULT 'draft'::character varying NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    planned_date date,
    completed_at timestamp with time zone,
    needs_review boolean DEFAULT false NOT NULL,
    CONSTRAINT trips_status_check CHECK (((status)::text = ANY ((ARRAY['draft'::character varying, 'saved'::character varying, 'completed'::character varying, 'reviewed'::character varying])::text[])))
);


--
-- Name: user_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_items (
    user_id uuid NOT NULL,
    item_id uuid NOT NULL
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id uuid NOT NULL,
    email character varying NOT NULL,
    hashed_password character varying,
    name character varying NOT NULL,
    avatar_url character varying,
    home_location text,
    timezone character varying,
    created_at timestamp without time zone,
    google_sub text,
    auth_provider text DEFAULT 'password'::text NOT NULL
);


--
-- Name: hike_completions hike_completions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hike_completions
    ADD CONSTRAINT hike_completions_pkey PRIMARY KEY (trip_id);


--
-- Name: hike_gear_requirements hike_gear_requirements_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hike_gear_requirements
    ADD CONSTRAINT hike_gear_requirements_pkey PRIMARY KEY (id);


--
-- Name: hikes hikes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hikes
    ADD CONSTRAINT hikes_pkey PRIMARY KEY (id);


--
-- Name: items items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.items
    ADD CONSTRAINT items_pkey PRIMARY KEY (id);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: trip_gear trip_gear_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trip_gear
    ADD CONSTRAINT trip_gear_pkey PRIMARY KEY (trip_id, item_id);


--
-- Name: trip_stops trip_stops_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trip_stops
    ADD CONSTRAINT trip_stops_pkey PRIMARY KEY (id);


--
-- Name: trips trips_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trips
    ADD CONSTRAINT trips_pkey PRIMARY KEY (id);


--
-- Name: hike_gear_requirements uq_hike_gear; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hike_gear_requirements
    ADD CONSTRAINT uq_hike_gear UNIQUE (hike_id, gear_tag);


--
-- Name: user_items user_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_items
    ADD CONSTRAINT user_items_pkey PRIMARY KEY (user_id, item_id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_google_sub_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_google_sub_key UNIQUE (google_sub);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: hikes_can_camp_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX hikes_can_camp_idx ON public.hikes USING btree (id) WHERE (can_camp = true);


--
-- Name: hikes_difficulty_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX hikes_difficulty_idx ON public.hikes USING btree (difficulty);


--
-- Name: hikes_lat_lng_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX hikes_lat_lng_idx ON public.hikes USING btree (lat, lng);


--
-- Name: hikes_region_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX hikes_region_idx ON public.hikes USING btree (region);


--
-- Name: hikes_tags_gin; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX hikes_tags_gin ON public.hikes USING gin (tags);


--
-- Name: idx_hike_gear_gear_tag; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_hike_gear_gear_tag ON public.hike_gear_requirements USING btree (gear_tag);


--
-- Name: idx_hike_gear_hike_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_hike_gear_hike_id ON public.hike_gear_requirements USING btree (hike_id);


--
-- Name: idx_hikes_state; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_hikes_state ON public.hikes USING btree (state);


--
-- Name: items_item_type_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX items_item_type_idx ON public.items USING btree (item_type);


--
-- Name: trips_needs_review_scan_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX trips_needs_review_scan_idx ON public.trips USING btree (completed_at) WHERE (((status)::text = 'completed'::text) AND (needs_review = false));


--
-- Name: trips_user_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX trips_user_id_idx ON public.trips USING btree (user_id);


--
-- Name: hike_completions hike_completions_trip_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hike_completions
    ADD CONSTRAINT hike_completions_trip_id_fkey FOREIGN KEY (trip_id) REFERENCES public.trips(id) ON DELETE CASCADE;


--
-- Name: hike_gear_requirements hike_gear_requirements_hike_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hike_gear_requirements
    ADD CONSTRAINT hike_gear_requirements_hike_id_fkey FOREIGN KEY (hike_id) REFERENCES public.hikes(id) ON DELETE CASCADE;


--
-- Name: trip_gear trip_gear_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trip_gear
    ADD CONSTRAINT trip_gear_item_id_fkey FOREIGN KEY (item_id) REFERENCES public.items(id);


--
-- Name: trip_gear trip_gear_trip_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trip_gear
    ADD CONSTRAINT trip_gear_trip_id_fkey FOREIGN KEY (trip_id) REFERENCES public.trips(id) ON DELETE CASCADE;


--
-- Name: trip_stops trip_stops_trip_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trip_stops
    ADD CONSTRAINT trip_stops_trip_id_fkey FOREIGN KEY (trip_id) REFERENCES public.trips(id) ON DELETE CASCADE;


--
-- Name: trips trips_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trips
    ADD CONSTRAINT trips_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_items user_items_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_items
    ADD CONSTRAINT user_items_item_id_fkey FOREIGN KEY (item_id) REFERENCES public.items(id) ON DELETE CASCADE;


--
-- Name: user_items user_items_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_items
    ADD CONSTRAINT user_items_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

