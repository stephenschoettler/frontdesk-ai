/*
   REFRESHED SETUP SCRIPT (v5 - Phase 2 Ready):
   - Includes configuration columns for Models & Tools.
   - Secure RLS enabled by default.
 */

---------------------------------
-- STEP 1: Drop tables in order
---------------------------------
DROP TABLE IF EXISTS "public"."conversations";
DROP TABLE IF EXISTS "public"."contacts";
DROP TABLE IF EXISTS "public"."clients";


---------------------------------
-- STEP 2: Create 'clients' table
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
    "stt_model" text DEFAULT 'nova-2-phonecall',
    "tts_model" text DEFAULT 'eleven_flash_v2_5',
    "tts_voice_id" text NOT NULL DEFAULT '21m00Tcm4TlvDq8ikWAM',
    -- Tools Configuration
    "enabled_tools" text[] DEFAULT '{get_available_slots,book_appointment,save_contact_name}',
    -- Prompting
    "initial_greeting" text,
    "system_prompt" text
);


---------------------------------
-- STEP 3: Create 'contacts' and 'conversations'
---------------------------------
-- Contacts
CREATE TABLE "public"."contacts" (
    "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    "client_id" uuid REFERENCES "public"."clients"("id") ON DELETE SET NULL,
    "phone" text NOT NULL,
    "name" text,
    "created_at" timestamp WITH TIME ZONE DEFAULT NOW(),
    UNIQUE("phone", "client_id")
);
CREATE INDEX "idx_contacts_phone" ON "public"."contacts" ("phone");

-- Conversations
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
-- STEP 5: Enable Row Level Security
---------------------------------
ALTER TABLE "public"."clients" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "public"."contacts" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "public"."conversations" ENABLE ROW LEVEL SECURITY;
