


SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;


COMMENT ON SCHEMA "public" IS 'standard public schema';



CREATE EXTENSION IF NOT EXISTS "pg_graphql" WITH SCHEMA "graphql";






CREATE EXTENSION IF NOT EXISTS "pg_stat_statements" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "pgcrypto" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "supabase_vault" WITH SCHEMA "vault";






CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA "extensions";






CREATE OR REPLACE FUNCTION "public"."get_client_usage_stats"() RETURNS TABLE("client_id" "text", "seconds_today" bigint, "seconds_month" bigint)
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    RETURN QUERY
    SELECT
        ul.client_id::text,
        COALESCE(SUM(CASE WHEN ul.created_at >= CURRENT_DATE THEN ul.quantity ELSE 0 END), 0)::bigint AS seconds_today,
        COALESCE(SUM(CASE WHEN ul.created_at >= DATE_TRUNC('month', CURRENT_DATE) THEN ul.quantity ELSE 0 END), 0)::bigint AS seconds_month
    FROM usage_ledger ul
    WHERE ul.metric_type IN ('duration', 'call_seconds')
    GROUP BY ul.client_id;
END;
$$;


ALTER FUNCTION "public"."get_client_usage_stats"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_daily_financials"("days_history" integer DEFAULT 30) RETURNS TABLE("date" "date", "total_revenue" numeric, "total_cost" numeric, "gross_profit" numeric)
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    RETURN QUERY
    SELECT
        DATE(ul.created_at) AS date,
        COALESCE(SUM(ul.revenue_usd), 0) AS total_revenue,
        COALESCE(SUM(ul.cost_usd), 0) AS total_cost,
        COALESCE(SUM(ul.revenue_usd) - SUM(ul.cost_usd), 0) AS gross_profit
    FROM public.usage_ledger ul
    WHERE ul.created_at >= CURRENT_DATE - days_history
    GROUP BY DATE(ul.created_at)
    ORDER BY date DESC;
END;
$$;


ALTER FUNCTION "public"."get_daily_financials"("days_history" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_global_usage_stats"() RETURNS TABLE("total_seconds_today" bigint, "total_seconds_month" bigint)
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    RETURN QUERY
    SELECT
        COALESCE(SUM(CASE WHEN ul.created_at >= CURRENT_DATE THEN ul.quantity ELSE 0 END), 0)::bigint AS total_seconds_today,
        COALESCE(SUM(CASE WHEN ul.created_at >= DATE_TRUNC('month', CURRENT_DATE) THEN ul.quantity ELSE 0 END), 0)::bigint AS total_seconds_month
    FROM usage_ledger ul
    WHERE ul.metric_type IN ('duration', 'call_seconds');
END;
$$;


ALTER FUNCTION "public"."get_global_usage_stats"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."handle_new_user"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
BEGIN
  INSERT INTO public.users (id, email)
  VALUES (new.id, new.email);
  RETURN new;
END;
$$;


ALTER FUNCTION "public"."handle_new_user"() OWNER TO "postgres";

SET default_tablespace = '';

SET default_table_access_method = "heap";


CREATE TABLE IF NOT EXISTS "public"."clients" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "owner_user_id" "uuid" NOT NULL,
    "name" "text",
    "cell" "text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "calendar_id" "text",
    "business_timezone" "text" DEFAULT 'America/Los_Angeles'::"text" NOT NULL,
    "business_start_hour" integer DEFAULT 9 NOT NULL,
    "business_end_hour" integer DEFAULT 17 NOT NULL,
    "llm_model" "text" DEFAULT 'openai/gpt-4o-mini'::"text" NOT NULL,
    "stt_model" "text" DEFAULT 'nova-2-phonecall'::"text",
    "tts_model" "text" DEFAULT 'eleven_flash_v2_5'::"text",
    "tts_voice_id" "text" DEFAULT '21m00Tcm4TlvDq8ikWAM'::"text" NOT NULL,
    "enabled_tools" "text"[] DEFAULT '{get_available_slots,book_appointment,reschedule_appointment,cancel_appointment,save_contact_name,list_my_appointments}'::"text"[],
    "initial_greeting" "text",
    "system_prompt" "text",
    "is_active" boolean DEFAULT true,
    "balance_seconds" integer DEFAULT 600
);


ALTER TABLE "public"."clients" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."contacts" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "client_id" "uuid",
    "phone" "text" NOT NULL,
    "name" "text",
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."contacts" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."conversations" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "client_id" "uuid",
    "contact_id" "uuid",
    "transcript" "jsonb",
    "summary" "text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "duration" integer DEFAULT 0
);


ALTER TABLE "public"."conversations" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."model_prices" (
    "id" "text" NOT NULL,
    "input_price" numeric,
    "output_price" numeric,
    "per_request_price" numeric DEFAULT 0,
    "image_price" numeric DEFAULT 0,
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."model_prices" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."system_settings" (
    "key" "text" NOT NULL,
    "value" "text" NOT NULL,
    "description" "text"
);


ALTER TABLE "public"."system_settings" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."usage_ledger" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "client_id" "uuid",
    "conversation_id" "uuid",
    "metric_type" "text" NOT NULL,
    "quantity" integer NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "cost_usd" numeric,
    "revenue_usd" numeric DEFAULT 0
);


ALTER TABLE "public"."usage_ledger" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."users" (
    "id" "uuid" NOT NULL,
    "email" "text",
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."users" OWNER TO "postgres";


ALTER TABLE ONLY "public"."clients"
    ADD CONSTRAINT "clients_cell_key" UNIQUE ("cell");



ALTER TABLE ONLY "public"."clients"
    ADD CONSTRAINT "clients_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."contacts"
    ADD CONSTRAINT "contacts_phone_client_id_key" UNIQUE ("phone", "client_id");



ALTER TABLE ONLY "public"."contacts"
    ADD CONSTRAINT "contacts_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."conversations"
    ADD CONSTRAINT "conversations_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."model_prices"
    ADD CONSTRAINT "model_prices_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."system_settings"
    ADD CONSTRAINT "system_settings_pkey" PRIMARY KEY ("key");



ALTER TABLE ONLY "public"."contacts"
    ADD CONSTRAINT "unique_phone_number" UNIQUE ("phone");



ALTER TABLE ONLY "public"."usage_ledger"
    ADD CONSTRAINT "usage_ledger_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."users"
    ADD CONSTRAINT "users_pkey" PRIMARY KEY ("id");



CREATE INDEX "idx_contacts_phone" ON "public"."contacts" USING "btree" ("phone");



CREATE INDEX "idx_conversations_client_id" ON "public"."conversations" USING "btree" ("client_id");



CREATE INDEX "idx_conversations_contact_id" ON "public"."conversations" USING "btree" ("contact_id");



ALTER TABLE ONLY "public"."clients"
    ADD CONSTRAINT "clients_owner_user_id_fkey" FOREIGN KEY ("owner_user_id") REFERENCES "public"."users"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."contacts"
    ADD CONSTRAINT "contacts_client_id_fkey" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."conversations"
    ADD CONSTRAINT "conversations_client_id_fkey" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."conversations"
    ADD CONSTRAINT "conversations_contact_id_fkey" FOREIGN KEY ("contact_id") REFERENCES "public"."contacts"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."usage_ledger"
    ADD CONSTRAINT "usage_ledger_client_id_fkey" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."usage_ledger"
    ADD CONSTRAINT "usage_ledger_conversation_id_fkey" FOREIGN KEY ("conversation_id") REFERENCES "public"."conversations"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."users"
    ADD CONSTRAINT "users_id_fkey" FOREIGN KEY ("id") REFERENCES "auth"."users"("id") ON DELETE CASCADE;



CREATE POLICY "Allow public read access" ON "public"."model_prices" FOR SELECT USING (true);



CREATE POLICY "Users can only SELECT, INSERT, UPDATE, DELETE their own clients" ON "public"."clients" USING (("owner_user_id" = "auth"."uid"())) WITH CHECK (("owner_user_id" = "auth"."uid"()));



CREATE POLICY "Users can only access contacts where the associated client_id b" ON "public"."contacts" USING (("client_id" IN ( SELECT "clients"."id"
   FROM "public"."clients"
  WHERE ("clients"."owner_user_id" = "auth"."uid"()))));



CREATE POLICY "Users can only access conversations linked to their clients." ON "public"."conversations" USING (("client_id" IN ( SELECT "clients"."id"
   FROM "public"."clients"
  WHERE ("clients"."owner_user_id" = "auth"."uid"()))));



CREATE POLICY "Users can view their own usage." ON "public"."usage_ledger" USING (("client_id" IN ( SELECT "clients"."id"
   FROM "public"."clients"
  WHERE ("clients"."owner_user_id" = "auth"."uid"()))));



ALTER TABLE "public"."clients" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."contacts" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."conversations" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."model_prices" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."usage_ledger" ENABLE ROW LEVEL SECURITY;




ALTER PUBLICATION "supabase_realtime" OWNER TO "postgres";


GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";

























































































































































GRANT ALL ON FUNCTION "public"."get_client_usage_stats"() TO "anon";
GRANT ALL ON FUNCTION "public"."get_client_usage_stats"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_client_usage_stats"() TO "service_role";



GRANT ALL ON FUNCTION "public"."get_daily_financials"("days_history" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."get_daily_financials"("days_history" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_daily_financials"("days_history" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."get_global_usage_stats"() TO "anon";
GRANT ALL ON FUNCTION "public"."get_global_usage_stats"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_global_usage_stats"() TO "service_role";



GRANT ALL ON FUNCTION "public"."handle_new_user"() TO "anon";
GRANT ALL ON FUNCTION "public"."handle_new_user"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."handle_new_user"() TO "service_role";


















GRANT ALL ON TABLE "public"."clients" TO "anon";
GRANT ALL ON TABLE "public"."clients" TO "authenticated";
GRANT ALL ON TABLE "public"."clients" TO "service_role";



GRANT ALL ON TABLE "public"."contacts" TO "anon";
GRANT ALL ON TABLE "public"."contacts" TO "authenticated";
GRANT ALL ON TABLE "public"."contacts" TO "service_role";



GRANT ALL ON TABLE "public"."conversations" TO "anon";
GRANT ALL ON TABLE "public"."conversations" TO "authenticated";
GRANT ALL ON TABLE "public"."conversations" TO "service_role";



GRANT ALL ON TABLE "public"."model_prices" TO "anon";
GRANT ALL ON TABLE "public"."model_prices" TO "authenticated";
GRANT ALL ON TABLE "public"."model_prices" TO "service_role";



GRANT ALL ON TABLE "public"."system_settings" TO "anon";
GRANT ALL ON TABLE "public"."system_settings" TO "authenticated";
GRANT ALL ON TABLE "public"."system_settings" TO "service_role";



GRANT ALL ON TABLE "public"."usage_ledger" TO "anon";
GRANT ALL ON TABLE "public"."usage_ledger" TO "authenticated";
GRANT ALL ON TABLE "public"."usage_ledger" TO "service_role";



GRANT ALL ON TABLE "public"."users" TO "anon";
GRANT ALL ON TABLE "public"."users" TO "authenticated";
GRANT ALL ON TABLE "public"."users" TO "service_role";









ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "service_role";































