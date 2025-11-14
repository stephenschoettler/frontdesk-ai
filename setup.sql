/*
  FRESH SETUP SCRIPT:
  - Drops all tables (old and new) to ensure a clean start.
  - Creates the 'clients' and 'bookings' tables.
  - Enables Row Level Security (RLS) and adds dev policies.
*/

-- STEP 1: Drop tables in order (dependents first)
DROP TABLE IF EXISTS "public"."bookings";
DROP TABLE IF EXISTS "public"."conversations";
DROP TABLE IF EXISTS "public"."clients";
DROP TABLE IF EXISTS "public"."users";
DROP TABLE IF EXISTS "public"."contacts";

-- STEP 2: Create the 'clients' table (The AI's owner)
CREATE TABLE "public"."clients" (
    "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    "name" text,
    "cell" text UNIQUE,
    "calendar_id" text,
    "created_at" timestamp WITH TIME ZONE DEFAULT NOW()
);

-- STEP 3: Create the 'bookings' table (The call log)
CREATE TABLE "public"."bookings" (
    "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    "client_id" uuid REFERENCES "public"."clients"("id") ON DELETE SET NULL,
    "service" text,
    "day" text,
    "time" text,
    "name" text,
    "phone" text,
    "transcript" text,
    "created_at" timestamp WITH TIME ZONE DEFAULT NOW()
);

-- STEP 4: Enable Row Level Security (CRITICAL)
ALTER TABLE "public"."clients" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "public"."bookings" ENABLE ROW LEVEL SECURITY;

-- STEP 5: Create development policies
CREATE POLICY "Allow anon access"
ON "public"."clients"
FOR ALL
USING (true)
WITH CHECK (true);

CREATE POLICY "Allow anon access"
ON "public"."bookings"
FOR ALL
USING (true)
WITH CHECK (true);
