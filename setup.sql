/*
  FRESH SETUP SCRIPT (v2 - 3-Table Model):
  - Drops all tables (old and new) to ensure a clean start.
  - Creates 'clients', 'contacts', and 'conversations' tables.
  - Enables Row Level Security (RLS) and adds dev policies.
*/

-- STEP 1: Drop tables in order (dependents first)
DROP TABLE IF EXISTS "public"."bookings"; -- Old table
DROP TABLE IF EXISTS "public"."conversations";
DROP TABLE IF EXISTS "public"."contacts";
DROP TABLE IF EXISTS "public"."clients";

-- STEP 2: Create the 'clients' table (The AI's owner/B2B customer)
CREATE TABLE "public"."clients" (
    "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    "name" text,
    "cell" text UNIQUE,
    "calendar_id" text,
    "created_at" timestamp WITH TIME ZONE DEFAULT NOW()
);

-- STEP 3: Create the 'contacts' table (The caller)
CREATE TABLE "public"."contacts" (
    "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    "client_id" uuid REFERENCES "public"."clients"("id") ON DELETE SET NULL,
    "phone" text UNIQUE NOT NULL,
    "name" text,
    "created_at" timestamp WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX "idx_contacts_phone" ON "public"."contacts" ("phone");

-- STEP 4: Create the 'conversations' table (The call log)
CREATE TABLE "public"."conversations" (
    "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    "client_id" uuid REFERENCES "public"."clients"("id") ON DELETE SET NULL,
    "contact_id" uuid REFERENCES "public"."contacts"("id") ON DELETE SET NULL,
    "transcript" jsonb,
    "summary" text,
    "created_at" timestamp WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX "idx_conversations_contact_id" ON "public"."conversations" ("contact_id");
CREATE INDEX "idx_conversations_client_id" ON "public"."conversations" ("client_id");

-- STEP 5: Enable Row Level Security (CRITICAL)
ALTER TABLE "public"."clients" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "public"."contacts" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "public"."conversations" ENABLE ROW LEVEL SECURITY;

-- STEP 6: Create development policies
CREATE POLICY "Allow anon access"
ON "public"."clients"
FOR ALL
USING (true)
WITH CHECK (true);

CREATE POLICY "Allow anon access"
ON "public" ."contacts"
FOR ALL
USING (true)
WITH CHECK (true);

CREATE POLICY "Allow anon access"
ON "public"."conversations"
FOR ALL
USING (true)
WITH CHECK (true);
