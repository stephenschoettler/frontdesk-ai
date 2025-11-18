/*
   REFRESHED SETUP SCRIPT (v3 - Config-Driven, Cleaned):
   - Drops only the three current production tables.
   - Creates 'clients' table with configuration columns.
   - Creates 'contacts' and 'conversations' tables.
   - Enables Row Level Security (RLS) and adds dev policies.
 */

---------------------------------
-- STEP 1: Drop tables in order (dependents first)
---------------------------------
DROP TABLE IF EXISTS "public"."conversations";
DROP TABLE IF EXISTS "public"."contacts";
DROP TABLE IF EXISTS "public"."clients";


---------------------------------
-- STEP 2: Create the 'clients' table (The AI's Owner & Configuration)
---------------------------------
CREATE TABLE "public"."clients" (
    "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    "name" text,
    "cell" text UNIQUE,
    "created_at" timestamp WITH TIME ZONE DEFAULT NOW(),
    -- Calendar Settings
    "calendar_id" text,
    "business_timezone" text NOT NULL DEFAULT 'America/Los_Angeles',
    "business_start_hour" integer NOT NULL DEFAULT 9,
    "business_end_hour" integer NOT NULL DEFAULT 17,
    -- AI/LLM Settings
    "llm_model" text NOT NULL DEFAULT 'openai/gpt-4o-mini',
    "tts_voice_id" text NOT NULL DEFAULT '21m00Tcm4TlvDq8ikWAM',
    "initial_greeting" text,
    "system_prompt" text
);


---------------------------------
-- STEP 3: Create 'contacts' and 'conversations' tables
---------------------------------
-- Contacts (The caller)
CREATE TABLE "public"."contacts" (
    "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    "client_id" uuid REFERENCES "public"."clients"("id") ON DELETE SET NULL,
    "phone" text UNIQUE NOT NULL,
    "name" text,
    "created_at" timestamp WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX "idx_contacts_phone" ON "public"."contacts" ("phone");

-- Conversations (The call log)
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


---------------------------------
-- STEP 5: Enable Row Level Security (CRITICAL)
---------------------------------
ALTER TABLE "public"."clients" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "public"."contacts" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "public"."conversations" ENABLE ROW LEVEL SECURITY;


---------------------------------
-- STEP 6: Create development policies
---------------------------------
CREATE POLICY "Allow anon access to clients"
ON "public"."clients"
FOR ALL
USING (true)
WITH CHECK (true);

CREATE POLICY "Allow anon access to contacts"
ON "public" ."contacts"
FOR ALL
USING (true)
WITH CHECK (true);

CREATE POLICY "Allow anon access to conversations"
ON "public"."conversations"
FOR ALL
USING (true)
WITH CHECK (true);
