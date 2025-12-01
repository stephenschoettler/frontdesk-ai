/*
   FRONTDESK AI - MASTER SETUP SCRIPT (v6 - Production)
   - Auth & Public User Sync (Fixes "Split Brain" issue)
   - Billing & Metering (Usage Ledger)
   - Role Based Security (RLS)
*/

-- 1. RESET (Be careful running this in prod!)
DROP TABLE IF EXISTS "public"."usage_ledger";
DROP TABLE IF EXISTS "public"."conversations";
DROP TABLE IF EXISTS "public"."contacts";
DROP TABLE IF EXISTS "public"."clients";
DROP TABLE IF EXISTS "public"."users";

-- 2. EXTENSIONS
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 3. USERS (Public Profile Sync)
CREATE TABLE "public"."users" (
    "id" uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    "email" text,
    "created_at" timestamp WITH TIME ZONE DEFAULT NOW()
);
ALTER TABLE "public"."users" ENABLE ROW LEVEL SECURITY;

-- 4. CLIENTS (The Wallets)
CREATE TABLE "public"."clients" (
    "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    "owner_user_id" uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    "name" text,
    "cell" text UNIQUE,
    "is_active" boolean DEFAULT true,
    "created_at" timestamp WITH TIME ZONE DEFAULT NOW(),
    -- Balance & Billing
    "balance_seconds" integer DEFAULT 600, 
    -- Configuration
    "calendar_id" text,
    "business_timezone" text DEFAULT 'America/Los_Angeles',
    "business_start_hour" integer DEFAULT 9,
    "business_end_hour" integer DEFAULT 17,
    -- AI Settings
    "llm_model" text DEFAULT 'openai/gpt-4o-mini',
    "stt_model" text DEFAULT 'nova-2-phonecall',
    "tts_model" text DEFAULT 'eleven_flash_v2_5',
    "tts_voice_id" text DEFAULT '21m00Tcm4TlvDq8ikWAM',
    "enabled_tools" text[] DEFAULT '{get_available_slots,book_appointment,reschedule_appointment,cancel_appointment,save_contact_name,list_my_appointments}',
    "initial_greeting" text,
    "system_prompt" text
);
ALTER TABLE "public"."clients" ENABLE ROW LEVEL SECURITY;

-- 5. CONTACTS & CONVERSATIONS
CREATE TABLE "public"."contacts" (
    "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    "client_id" uuid REFERENCES "public"."clients"("id") ON DELETE SET NULL,
    "phone" text NOT NULL,
    "name" text,
    "created_at" timestamp WITH TIME ZONE DEFAULT NOW(),
    UNIQUE("phone", "client_id")
);
ALTER TABLE "public"."contacts" ENABLE ROW LEVEL SECURITY;

CREATE TABLE "public"."conversations" (
    "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    "client_id" uuid REFERENCES "public"."clients"("id") ON DELETE SET NULL,
    "contact_id" uuid REFERENCES "public"."contacts"("id") ON DELETE SET NULL,
    "transcript" jsonb,
    "summary" text,
    "created_at" timestamp WITH TIME ZONE DEFAULT NOW(),
    "duration" integer DEFAULT 0
);
ALTER TABLE "public"."conversations" ENABLE ROW LEVEL SECURITY;

-- 6. THE METER (Usage Ledger)
CREATE TABLE "public"."usage_ledger" (
    "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    "client_id" uuid REFERENCES "public"."clients"("id") ON DELETE CASCADE,
    "conversation_id" uuid REFERENCES "public"."conversations"("id") ON DELETE SET NULL,
    "metric_type" text NOT NULL, -- 'call_duration', 'llm_tokens_input', etc
    "quantity" integer NOT NULL,
    "created_at" timestamp WITH TIME ZONE DEFAULT NOW()
);
ALTER TABLE "public"."usage_ledger" ENABLE ROW LEVEL SECURITY;

-- 7. AUTOMATION: User Sync Trigger (CRITICAL FIX)
-- This ensures every new Auth user gets a Public User record automatically.
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.users (id, email)
  VALUES (new.id, new.email);
  RETURN new;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();

-- 8. SECURITY POLICIES (RLS)
-- Users
CREATE POLICY "Users can view their own profile" ON "public"."users"
    USING (id = auth.uid());

-- Clients
CREATE POLICY "Users can only access their own clients" ON "public"."clients"
    USING (owner_user_id = auth.uid())
    WITH CHECK (owner_user_id = auth.uid());

-- Contacts (Linked via Client)
CREATE POLICY "Users can access contacts of their clients" ON "public"."contacts"
    USING (client_id IN (SELECT id FROM clients WHERE owner_user_id = auth.uid()));

-- Conversations (Linked via Client)
CREATE POLICY "Users can access conversations of their clients" ON "public"."conversations"
    USING (client_id IN (SELECT id FROM clients WHERE owner_user_id = auth.uid()));

-- Usage Ledger (Linked via Client)
CREATE POLICY "Users can view their own usage" ON "public"."usage_ledger"
    USING (client_id IN (SELECT id FROM clients WHERE owner_user_id = auth.uid()));
