console.log("App.js loaded, checking Vue...");

// Check if Vue is loaded
if (
  typeof Vue === "undefined" ||
  typeof Vue.createApp === "undefined" ||
  typeof axios === "undefined" ||
  typeof bootstrap === "undefined"
) {
  console.error(
    "Vue.js, Axios, or Bootstrap is not loaded. Please check your internet connection and try refreshing the page.",
  );
  document.getElementById("app").innerHTML =
    '<div class="alert alert-danger">Critical libraries (Vue.js, Axios, or Bootstrap) failed to load. Please check your internet connection and refresh the page.</div>';
} else {
  const { createApp, ref, computed, onMounted, watch, nextTick } = Vue;

  Vue.createApp({
    setup() {
      console.log("Vue setup running...");
      const authToken = ref(localStorage.getItem("authToken"));
      const currentUser = ref(null);
      const currentView = ref(authToken.value ? "dashboard" : "landing");

      const clients = ref([]);
      const filteredClients = ref([]);
      const selectedClients = ref([]);

      const allSelected = computed(() => {
        if (filteredClients.value.length === 0) return false;
        return filteredClients.value.every((client) =>
          selectedClients.value.includes(client.id),
        );
      });
      const selectedCallLogs = ref([]);
      const searchQuery = ref("");
      const filterStatus = ref("");
      const sortBy = ref("name");
      const currentPage = ref(1);
      const pageSize = ref(12);
      const showCreateModal = ref(false);
      const showEditModal = ref(false);
      const showBulkModal = ref(false);
      const showEditContactModal = ref(false);
      const showSettingsModal = ref(false);
      const showUserProfileModal = ref(false);
      const showTopUpModal = ref(false);
      const selectedTopUpClient = ref(null);
      const savingProfile = ref(false);
      const userProfile = ref({
        displayName: "",
        currentPassword: "",
        newPassword: "",
        confirmPassword: "",
      });
      const showSubscriptionModal = ref(false);
      const showProvisionModal = ref(false);
      const showAuthModal = ref(false);
      const provisioningClient = ref(null);
      const showAuditLog = ref(false);
      const auditModal = ref(null);
      const openAuditLog = () => auditModal.value?.show();
      const closeAuditLog = () => auditModal.value?.hide();
      const systemPromptExpanded = ref(false);
      const showUserMenu = ref(false);
      const bulkSelectMode = ref(false);
      const saving = ref(false);
      const savingContact = ref(false);
      const selectedTemplate = ref("");
      const templates = ref({});

      // Calendar authentication state
      const calendarAuthStatus = ref({
        has_credentials: false,
        credential_type: null,
        fallback_available: false,
        service_account_email: null,
        last_used_at: null
      });
      const initiatingOAuth = ref(false);
      const serviceAccountFile = ref(null);
      const uploadingServiceAccount = ref(false);
      const revokingCredentials = ref(false);

      // Google OAuth login state
      const googleLoginInProgress = ref(false);

      // Voice presets by provider
      const elevenlabsVoices = [
        { name: "Rachel (American, Calm, Pro)", id: "21m00Tcm4TlvDq8ikWAM" },
        { name: "Drew (American, News, Bold)", id: "29vD33N1CtxCmqQRPOHJ" },
        { name: "Clyde (Deep, Technical)", id: "2EiwWnXFnvU5JabPnv8n" },
        { name: "Mimi (Australian, Childish)", id: "zrHiDhphv9ZnVXBq79M6" },
        { name: "Fin (Irish, Energetic)", id: "D38z5RcWu1voky8WS1ja" },
        { name: "Antoni (American, Well-rounded)", id: "ErXwobaYiN019PkySvjV" },
        { name: "Thomas (American, Calm)", id: "GBv7mTt5Xyp17vW9q545" },
        { name: "Charlie (Australian, Casual)", id: "IKne3meq5aSn9XLyUdCD" },
        { name: "Emily (American, Calm)", id: "LcfcDJNUP1GQjkzn1xUU" },
        { name: "Elli (American, Emotional)", id: "MF3mGyEYCl7XYWbV9V6O" },
        { name: "Callum (American, Hoarse)", id: "N2lVS1w4Ejp13nTc3DX7" },
        { name: "Patrick (American, Shouty)", id: "ODq5zmih8GrVes37Dizd" },
        { name: "Harry (American, Anxiety)", id: "SOYHLrjzK2X1ezoPC6cr" },
        { name: "Liam (American, Neutral)", id: "TX3LPaxmHKxFdv7VOQHJ" },
        { name: "Dorothy (British, Pleasant)", id: "ThT5KcBeYPX3keUQqHPh" },
        { name: "Josh (American, Deep)", id: "TxGEqnHWrfWFTfGW9XjX" },
        { name: "Arnold (American, Nasal)", id: "VR6AewLTigWg4xSOukaG" },
        { name: "Charlotte (British, Seductive)", id: "XB0fDUnXU5powFXDhCwa" },
        { name: "Matilda (American, Warm)", id: "XrExE9yKIg1WjnnlVkGX" },
        { name: "James (Australian, Calm)", id: "ZQe5CZNOzWyzPSCn5a3c" },
        { name: "Joseph (British, News)", id: "Zlb1dXrM653N07WRdFW3" },
        { name: "Jeremy (American, Excited)", id: "bVMeCyTHy58xNoL34h3p" },
        { name: "Michael (American, Old)", id: "flq6f7yk4E4fJM5XTYuZ" },
        { name: "Ethan (American, Whisper)", id: "g5CIjZEefAph4nQFvHAz" },
        { name: "Gigi (American, Childish)", id: "jBpfuIE2acCO8z3wKNLl" },
        { name: "Freya (American, Overhyped)", id: "jsCqWAovK2LkecY7zXl4" },
        { name: "Santa Claus (Deep, Jolly)", id: "knrPHWnBmmDHMoiMeP3l" },
        { name: "Grace (American, Southern)", id: "oWAxZDx7w5VEj9dCyTzz" },
        { name: "Daniel (British, News)", id: "onwK4e9ZLuTAKqWW03F9" },
        { name: "Serena (American, Pleasant)", id: "pMsXgVXv3BLzUgSXRplE" },
        { name: "Adam (American, Deep)", id: "pNInz6obpgDQGcFmaJgB" },
        { name: "Nicole (American, Whisper)", id: "piTKgcLEGmPE4e6mEKli" },
        { name: "Bill (American, Trustworthy)", id: "pqHfZKP75CvOlQylNhV4" },
        { name: "Jessie (American, Raspy)", id: "t0jbNlBVZ17f02VDIeMI" },
        { name: "Sam (American, Raspy)", id: "yoZ06aMxZJJ28mfd3POQ" },
        { name: "Glinda (American, Witch)", id: "z9fAnlkpzviPz146aGWa" },
        { name: "Giovanni (Italian, Foreign)", id: "zcAOhNBS3c14rBihAFp1" },
        { name: "Domi (American, Strong)", id: "zRrTh6t1l6l36r8e9a2W" },
      ];

      const cartesiaVoices = [
        { name: "Cindy - Receptionist", id: "1242fb95-7ddd-44ac-8a05-9e8a22a6137d" },
        { name: "Jacqueline - Reassuring Agent", id: "9626c31c-bec5-4cca-baa8-f8ba9e84c8bc" },
        { name: "Blake - Helpful Agent", id: "a167e0f3-df7e-4d52-a9c3-f949145efdab" },
        { name: "Brooke - Big Sister", id: "e07c00bc-4134-4eae-9ea4-1a55fb45746b" },
        { name: "Carson - Curious Conversationalist", id: "86e30c1d-714b-4074-a1f2-1cb6b552fb49" },
        { name: "Lauren - Lively Narrator", id: "a33f7a4c-100f-41cf-a1fd-5822e8fc253f" },
        { name: "Henry - Plainspoken Guy", id: "87286a8d-7ea7-4235-a41a-dd9fa6630feb" },
        { name: "Katie - Friendly Fixer", id: "f786b574-daa5-4673-aa0c-cbe3e8534c02" },
        { name: "Caroline - Southern Guide", id: "f9836c6e-a0bd-460e-9d3c-f7299fa60f94" },
        { name: "Ronald - Thinker", id: "5ee9feff-1265-424a-9d7f-8e4d431a12c7" },
        { name: "Riya - College Roommate", id: "faf0731e-dfb9-4cfc-8119-259a79b27e12" },
        { name: "Cathy - Coworker", id: "e8e5fffb-252c-436d-b842-8879b84445b6" },
        { name: "Theo - Modern Narrator", id: "79f8b5fb-2cc8-479a-80df-29f7a7cf1a3e" },
        { name: "Pedro - Formal Speaker", id: "15d0c2e2-8d29-44c3-be23-d585d5f154a1" },
        { name: "Jameson - Easygoing Support", id: "a5136bf9-224c-4d76-b823-52bd5efcffcc" },
        { name: "Parvati - Friendly Supporter", id: "bec003e2-3cb3-429c-8468-206a393c67ad" },
        { name: "Emilio - Friendly Optimist", id: "b0689631-eee7-4a6c-bb86-195f1d267c2e" },
        { name: "Daniela - Relaxed Woman", id: "5c5ad5e7-1020-476b-8b91-fdcbe9cc313c" },
        { name: "Sebastian - Orator", id: "b7187e84-fe22-4344-ba4a-bc013fcb533e" },
      ];

      // Computed property to show the right voice presets based on selected provider
      const voicePresets = computed(() => {
        return clientForm.value.tts_provider === 'cartesia' ? cartesiaVoices : elevenlabsVoices;
      });

      const importFile = ref(null);
      const activeClientTab = ref("basic"); // Added for tabbed UI

      // Twilio Provisioning State
      const availableNumbers = ref([]);
      const searchAreaCode = ref("");
      const searchingNumbers = ref(false);

      // Simulator State
      const simulatingClient = ref(null);
      const isSimulating = ref(false);
      const simulatorSocket = ref(null);
      const audioContext = ref(null);
      const simulatorModal = ref(null);
      const mediaStream = ref(null);
      const processor = ref(null);

      // SAFETY FIX: Handle corrupted storage gracefully
      let initialLogs = [];
      try {
        initialLogs = JSON.parse(localStorage.getItem("auditLogs") || "[]");
      } catch (e) {
        console.error("Resetting corrupted audit logs", e);
        initialLogs = [];
      }
      const auditLogs = ref(initialLogs);

      const activeTab = ref("clients");
      const activeCalls = ref([]); // LIVE CALLS
      const contacts = ref([]);
      const selectedContacts = ref([]);
      const callLogs = ref([]);
      const selectedTranscript = ref(null);
      const transcriptExpanded = ref(false);
      const isLoading = ref(false);

      const contactSearchQuery = ref("");
      const contactFilterClient = ref(""); // <--- ADD THIS
      const logSearchQuery = ref("");
      const logFilterClient = ref("");
      const logFilterContact = ref("");

      // Inline editing state for contacts
      const editingContactPhone = ref(null);
      const tempContactName = ref("");

      // Theme management
      const themes = ref([]);
      const currentTheme = ref(
        localStorage.getItem("currentTheme") || "tokyo-night-default",
      );

      // Auth related state
      const authForm = ref({
        email: "",
        password: "",
      });
      const authError = ref(null);
      const authSuccess = ref(null);

      const clientForm = ref({
        name: "",
        cell: "",
        calendar_id: "",
        business_timezone: "America/Los_Angeles",
        business_start_hour: 9,
        business_end_hour: 17,
        llm_model: "openai/gpt-4o-mini",
        stt_model: "nova-2-phonecall",
        tts_provider: "cartesia",
        tts_model: "eleven_flash_v2_5",
        tts_voice_id: "21m00Tcm4TlvDq8ikWAM",
        initial_greeting: "",
        system_prompt: "",
        enabled_tools: [],
        enable_scheduling: false,
        enable_contact_memory: false,
        is_active: true, // Default active for new clients
      });

      const editingClient = ref(null);
      const editingContact = ref({
        phone: "",
        name: "",
      });

      const totalPages = computed(() =>
        Math.ceil(filteredClients.value.length / pageSize.value),
      );
      const visiblePages = computed(() => {
        const pages = [];
        const start = Math.max(1, currentPage.value - 2);
        const end = Math.min(totalPages.value, currentPage.value + 2);
        for (let i = start; i <= end; i++) {
          pages.push(i);
        }
        return pages;
      });

      const paginatedClients = computed(() => {
        const start = (currentPage.value - 1) * pageSize.value;
        const end = start + pageSize.value;
        return filteredClients.value.slice(start, end);
      });

      // --- HELPER: Normalize Phone Numbers for Comparison ---
      const normalizePhone = (phone) => {
        if (!phone) return "";
        // Strip all non-digit characters
        return phone.replace(/\D/g, "");
      };

      const matchPhones = (p1, p2) => {
        if (!p1 || !p2) return false;
        const n1 = normalizePhone(p1);
        const n2 = normalizePhone(p2);
        // Robust match: exact match OR one contains the other (handles +1 vs no +1)
        return (
          n1 === n2 ||
          (n1.length > 6 &&
            n2.length > 6 &&
            (n1.includes(n2) || n2.includes(n1)))
        );
      };

      const filteredContacts = computed(() => {
        if (!contacts.value) return [];
        return contacts.value.filter((contact) => {
          const search = contactSearchQuery.value.toLowerCase();
          const cleanSearch = normalizePhone(search);

          // 1. Filter by Client (Exact Match on ID)
          const clientMatch =
            !contactFilterClient.value ||
            contact.client_id === contactFilterClient.value;

          // 2. Filter by Search (Name or Phone) - Robust Phone Match
          const searchMatch =
            (contact.name && contact.name.toLowerCase().includes(search)) ||
            contact.phone.toLowerCase().includes(search) ||
            (cleanSearch &&
              normalizePhone(contact.phone).includes(cleanSearch));

          return clientMatch && searchMatch;
        });
      });

      const allContactsSelected = computed(() => {
        if (filteredContacts.value.length === 0) return false;
        return filteredContacts.value.every((contact) =>
          selectedContacts.value.includes(contact.phone),
        );
      });

      const contactsSelectIndeterminate = computed(() => {
        if (filteredContacts.value.length === 0) return false;
        const selectedCount = filteredContacts.value.filter((contact) =>
          selectedContacts.value.includes(contact.phone),
        ).length;
        return (
          selectedCount > 0 && selectedCount < filteredContacts.value.length
        );
      });

      const filteredCallLogs = computed(() => {
        if (!callLogs.value) return [];
        return callLogs.value.filter((log) => {
          const search = logSearchQuery.value.toLowerCase();
          const clientName = clients.value.find(
            (c) => c.id === logFilterClient.value,
          )?.name;
          const clientMatch =
            !logFilterClient.value ||
            (clientName && log.client_name === clientName);

          // ROBUST CONTACT MATCHING
          const contactMatch =
            !logFilterContact.value ||
            matchPhones(log.phone, logFilterContact.value);

          // Find contact for name search (using robust match)
          const contact = contacts.value.find((c) =>
            matchPhones(c.phone, log.phone),
          );
          const contactName = contact ? contact.name : "";

          const searchMatch =
            !search ||
            (log.phone && log.phone.toLowerCase().includes(search)) ||
            (log.status && log.status.toLowerCase().includes(search)) ||
            (contactName && contactName.toLowerCase().includes(search));

          return clientMatch && searchMatch && contactMatch;
        });
      });

      const selectAllCallLogs = computed(() => {
        if (filteredCallLogs.value.length === 0) return false;
        return filteredCallLogs.value.every((log) =>
          selectedCallLogs.value.includes(log.id),
        );
      });

      const selectAllIndeterminate = computed(() => {
        if (filteredCallLogs.value.length === 0) return false;
        const selectedCount = filteredCallLogs.value.filter((log) =>
          selectedCallLogs.value.includes(log.id),
        ).length;
        return (
          selectedCount > 0 && selectedCount < filteredCallLogs.value.length
        );
      });

      // --- Auth Logic ---
      const setAuthToken = (token) => {
        authToken.value = token;
        if (token) {
          localStorage.setItem("authToken", token);
          axios.defaults.headers.common["Authorization"] = "Bearer " + token;
          try {
            const payload = JSON.parse(atob(token.split(".")[1]));
            currentUser.value = payload.email;
          } catch (e) {
            console.error("Error decoding token:", e);
            currentUser.value = "User";
          }
          currentView.value = "dashboard";
          showAuthModal.value = false;
        } else {
          localStorage.removeItem("authToken");
          delete axios.defaults.headers.common["Authorization"];
          currentUser.value = null;
          currentView.value = "landing";
        }
      };

      const login = async () => {
        authError.value = null;
        try {
          const response = await axios.post("/api/auth/login", authForm.value);
          setAuthToken(response.data.access_token);

          // --- THE RED CARPET ---
          // Check if the logged-in user is the admin
          if (currentUser.value === "admin@frontdesk.com") {
            console.log("Admin identified. Redirecting to Monitor.");
            window.location.href = "/static/monitor.html";
            return;
          }
          // ----------------------

          await loadClients();
        } catch (error) {
          console.error("Login failed:", error);
          authError.value =
            error.response?.data?.detail ||
            "Login failed. Please check your credentials.";
        }
      };

      const register = async () => {
        authError.value = null;
        authSuccess.value = null;
        try {
          const response = await axios.post(
            "/api/auth/register",
            authForm.value,
          );
          // Switch to login view and keep modal open
          currentView.value = "login";
          authForm.value.password = "";
          authSuccess.value = "Account created successfully! Please login.";
        } catch (error) {
          console.error("Registration failed:", error);
          authError.value =
            error.response?.data?.detail || "Registration failed.";
        }
      };

      const logout = () => {
        setAuthToken(null);
        clients.value = [];
        contacts.value = [];
        callLogs.value = [];
        selectedTranscript.value = null;
        alert("You have been logged out.");
      };

      const toggleAuthView = () => {
        authError.value = null;
        authSuccess.value = null;
        authForm.value.password = "";
        currentView.value =
          currentView.value === "login" ? "register" : "login";
      };

      const initiateGoogleLogin = async () => {
        googleLoginInProgress.value = true;
        try {
          const response = await axios.post("/api/auth/google/initiate");
          const authUrl = response.data.authorization_url;

          // Open Google OAuth popup
          const width = 500;
          const height = 600;
          const left = (screen.width - width) / 2;
          const top = (screen.height - height) / 2;

          const popup = window.open(
            authUrl,
            "GoogleLoginPopup",
            `width=${width},height=${height},left=${left},top=${top}`
          );

          // Listen for OAuth callback
          const messageHandler = async (event) => {
            if (event.data.type === "google_login_success") {
              window.removeEventListener("message", messageHandler);
              popup?.close();

              // Store auth token and user data
              const { user, token } = event.data;
              setAuthToken(token);
              currentUser.value = user;
              currentView.value = "dashboard";
              showAuthModal.value = false;

              // Clear auth form
              authForm.value.email = "";
              authForm.value.password = "";
              authError.value = null;

              // Load data
              await loadClients();
              await loadTemplates();
              await loadContacts();
              await loadCallLogs();

              console.log("Google login successful:", user.email);
            }
          };

          window.addEventListener("message", messageHandler);

          // Check if popup was blocked
          if (!popup || popup.closed) {
            alert("Popup was blocked. Please allow popups for this site and try again.");
            window.removeEventListener("message", messageHandler);
          }
        } catch (error) {
          console.error("Failed to initiate Google login:", error);
          authError.value = "Failed to initiate Google login. Please try again.";
        } finally {
          googleLoginInProgress.value = false;
        }
      };

      const loadClients = async () => {
        try {
          // Force network fetch to ensure fresh data
          // const localClients = localStorage.getItem("clients");
          // if (localClients) { ... }

          const response = await axios.get("/api/clients");

          clients.value = response.data.clients.map((c) => ({
            ...c,
            enabled_tools: c.enabled_tools || [],
            is_active: c.is_active !== undefined ? c.is_active : true, // Default to true if missing
          }));

          // Fetch calendar auth status for each client (in parallel)
          if (authToken.value) {
            const statusPromises = clients.value.map(async (client) => {
              try {
                const statusResponse = await axios.get(
                  `/api/clients/${client.id}/calendar/status`,
                  { headers: { Authorization: `Bearer ${authToken.value}` } }
                );
                client.calendar_auth_status = statusResponse.data;
              } catch (error) {
                // Silently fail for individual clients - they'll just show no status
                client.calendar_auth_status = null;
              }
            });
            await Promise.all(statusPromises);
          }

          // Update Local Storage
          localStorage.setItem("clients", JSON.stringify(clients.value));

          filterClients();
        } catch (error) {
          console.error("Failed to load clients:", error);
        }
      };

      const loadTemplates = async () => {
        try {
          const response = await axios.get("/api/templates");
          templates.value = response.data;
        } catch (error) {
          console.error("Failed to load templates:", error);
        }
      };

      const importClients = (event) => {
        const file = event.target.files[0];

        if (file) {
          const reader = new FileReader();

          reader.onload = (e) => {
            try {
              const data = JSON.parse(e.target.result);

              clients.value = Array.isArray(data.clients) ? data.clients : data;

              localStorage.setItem("clients", JSON.stringify(clients.value));

              filterClients();

              alert("Clients imported successfully!");
            } catch (err) {
              alert("Invalid JSON file");
            }
          };

          reader.readAsText(file);
        }
      };

      const filterClients = () => {
        let filtered = clients.value.filter((client) => {
          const matchesSearch =
            client.name
              .toLowerCase()
              .includes(searchQuery.value.toLowerCase()) ||
            (client.cell && client.cell.includes(searchQuery.value));

          // UPDATED: Filter by is_active status
          const matchesStatus =
            !filterStatus.value ||
            (filterStatus.value === "active" && client.is_active) ||
            (filterStatus.value === "inactive" && !client.is_active);

          return matchesSearch && matchesStatus;
        });

        filtered.sort((a, b) => {
          if (sortBy.value === "name") {
            return a.name.localeCompare(b.name);
          } else {
            return new Date(b.created_at) - new Date(a.created_at);
          }
        });

        filteredClients.value = filtered;
        currentPage.value = 1;
      };

      const sortClients = () => {
        filterClients();
      };

      const searchNumbers = async () => {
        if (!searchAreaCode.value) return;
        searchingNumbers.value = true;
        availableNumbers.value = [];
        try {
          const response = await axios.get(
            `/api/twilio/available-numbers?area_code=${searchAreaCode.value}`,
          );
          availableNumbers.value = response.data.numbers;
        } catch (error) {
          console.error("Failed to search numbers", error);
          alert("Failed to search numbers. Please check the area code.");
        } finally {
          searchingNumbers.value = false;
        }
      };

      const editClient = async (client) => {
        editingClient.value = client.id;
        const enabledTools = client.enabled_tools || [];
        clientForm.value = {
          ...client,
          enabled_tools: enabledTools,
          enable_scheduling: enabledTools.includes("book_appointment"),
          enable_contact_memory: enabledTools.includes("save_contact_name"),
          is_active: client.is_active !== undefined ? client.is_active : true,
          tts_provider: client.tts_provider || "cartesia",  // Default to Cartesia for existing clients
        };
        activeClientTab.value = "basic";
        showEditModal.value = true;

        // Fetch calendar auth status for this client
        await fetchCalendarAuthStatus(client.id);
      };

      const duplicateClient = (client) => {
        const duplicated = { ...client };
        delete duplicated.id;
        delete duplicated.created_at;
        duplicated.name += " (Copy)";
        const enabledTools = client.enabled_tools || [];
        duplicated.enabled_tools = enabledTools;
        duplicated.enable_scheduling =
          enabledTools.includes("book_appointment");
        duplicated.enable_contact_memory =
          enabledTools.includes("save_contact_name");
        duplicated.is_active = true; // Default copy to active
        editingClient.value = null;
        clientForm.value = duplicated;
        activeClientTab.value = "basic";
        showCreateModal.value = true;
      };

      const saveClient = async () => {
        saving.value = true;
        try {
          // Translate bundles to enabled_tools
          const payload = { ...clientForm.value };
          payload.enabled_tools = [];
          if (payload.enable_scheduling) {
            payload.enabled_tools.push(
              "get_available_slots",
              "book_appointment",
              "reschedule_appointment",
              "list_my_appointments",
              "cancel_appointment",
            );
          }
          if (payload.enable_contact_memory) {
            payload.enabled_tools.push("save_contact_name");
          }
          // Remove bundle fields from payload
          delete payload.enable_scheduling;
          delete payload.enable_contact_memory;

          // Provisioning Mapping - REMOVED (Pay First Flow)
          // if (!editingClient.value && payload.cell) {
          //    payload.selected_number = payload.cell;
          // }

          let response;
          if (editingClient.value) {
            response = await axios.put(
              `/api/clients/${editingClient.value}`,
              payload,
            );
            const index = clients.value.findIndex(
              (c) => c.id === editingClient.value,
            );
            clients.value[index] = response.data;
            addAuditLog("update", `Updated client: ${response.data.name}`);
            closeModal(); // Close edit modal normally
          } else {
            response = await axios.post("/api/clients", payload);
            clients.value.push(response.data);
            addAuditLog("create", `Created client: ${response.data.name}`);

            // SUBSCRIPTION FIRST FLOW
            // 1. Close Create Modal
            closeModal();
            // 2. Set context for checkout (reuse selectedTopUpClient for simplicity)
            selectedTopUpClient.value = response.data;

            // Track pending payment
            localStorage.setItem("pendingPaymentClientId", response.data.id);

            // 3. Open Subscription Modal
            showSubscriptionModal.value = true;
          }
          filterClients();
        } catch (error) {
          console.error("Failed to save client:", error);
          alert("Failed to save client");
        } finally {
          saving.value = false;
        }
      };

      const deleteClient = async (id) => {
        if (
          !confirm(
            "WARNING: This will permanently delete the AI Agent and release its phone number. Any remaining balance will be forfeited. This cannot be undone. Are you sure?",
          )
        )
          return;
        try {
          await axios.delete(`/api/clients/${id}`);
          clients.value = clients.value.filter((c) => c.id !== id);
          addAuditLog("delete", `Deleted client ID: ${id}`);
          filterClients();
        } catch (error) {
          console.error("Failed to delete client:", error);
          alert("Failed to delete client");
        }
      };

      const bulkDelete = async () => {
        if (
          !confirm(
            `Are you sure you want to delete ${selectedClients.value.length} clients?`,
          )
        )
          return;
        try {
          await Promise.all(
            selectedClients.value.map((id) =>
              axios.delete(`/api/clients/${id}`),
            ),
          );
          clients.value = clients.value.filter(
            (c) => !selectedClients.value.includes(c.id),
          );
          addAuditLog(
            "delete",
            `Bulk deleted ${selectedClients.value.length} clients`,
          );
          selectedClients.value = [];
          filterClients();
          showBulkModal.value = false;
        } catch (error) {
          console.error("Failed to bulk delete:", error);
          alert("Failed to bulk delete");
        }
      };

      const bulkUpdate = () => {
        alert("Bulk update not implemented yet");
      };

      // NEW: Toggle Client Status
      const toggleClientStatus = async (client) => {
        const newStatus = !client.is_active;
        const actionWord = newStatus ? "Enable" : "Disable";

        if (!confirm(`${actionWord} ${client.name}?`)) return;

        try {
          // Optimistic Update
          client.is_active = newStatus;

          await axios.put(`/api/clients/${client.id}`, {
            ...client,
            is_active: newStatus,
          });

          addAuditLog("update", `${actionWord}d client: ${client.name}`);
          filterClients(); // Re-apply filters
        } catch (error) {
          console.error("Failed to toggle status:", error);
          // Revert on failure
          client.is_active = !newStatus;
          alert(`Failed to ${actionWord.toLowerCase()} client.`);
        }
      };

      // Calendar Authentication Methods
      const fetchCalendarAuthStatus = async (clientId) => {
        try {
          const response = await axios.get(
            `/api/clients/${clientId}/calendar/status`,
            { headers: { Authorization: `Bearer ${authToken.value}` } }
          );
          calendarAuthStatus.value = response.data;
        } catch (error) {
          console.error("Failed to fetch calendar auth status:", error);
          calendarAuthStatus.value = {
            has_credentials: false,
            credential_type: null,
            fallback_available: false
          };
        }
      };

      const initiateOAuthFlow = async () => {
        if (!editingClient.value) return;

        initiatingOAuth.value = true;
        try {
          const response = await axios.post(
            `/api/clients/${editingClient.value}/calendar/oauth/initiate`,
            {},
            { headers: { Authorization: `Bearer ${authToken.value}` } }
          );

          const authUrl = response.data.authorization_url;

          // Open OAuth popup
          const width = 600;
          const height = 700;
          const left = (screen.width - width) / 2;
          const top = (screen.height - height) / 2;

          const popup = window.open(
            authUrl,
            'GoogleOAuthPopup',
            `width=${width},height=${height},left=${left},top=${top}`
          );

          // Listen for OAuth callback
          const messageHandler = async (event) => {
            if (event.data.type === 'oauth_success') {
              window.removeEventListener('message', messageHandler);
              popup?.close();

              // Refresh auth status
              await fetchCalendarAuthStatus(editingClient.value);
              alert('Calendar authentication successful!');
            }
          };

          window.addEventListener('message', messageHandler);

          // Check if popup was blocked
          if (!popup || popup.closed) {
            alert('Popup was blocked. Please allow popups for this site and try again.');
          }

        } catch (error) {
          console.error("Failed to initiate OAuth:", error);
          alert("Failed to initiate OAuth flow. Please try again.");
        } finally {
          initiatingOAuth.value = false;
        }
      };

      const handleServiceAccountFileSelect = (event) => {
        const file = event.target.files[0];
        if (file && file.type === 'application/json') {
          serviceAccountFile.value = file;
        } else {
          alert('Please select a valid JSON file.');
          event.target.value = '';
        }
      };

      const uploadServiceAccount = async () => {
        if (!editingClient.value || !serviceAccountFile.value) return;

        uploadingServiceAccount.value = true;
        try {
          const fileContent = await serviceAccountFile.value.text();

          // Validate JSON
          try {
            JSON.parse(fileContent);
          } catch (e) {
            alert('Invalid JSON file. Please check the file and try again.');
            return;
          }

          const response = await axios.post(
            `/api/clients/${editingClient.value}/calendar/service-account`,
            { service_account_json: fileContent },
            { headers: { Authorization: `Bearer ${authToken.value}` } }
          );

          // Clear file input
          serviceAccountFile.value = null;
          const fileInput = document.getElementById('serviceAccountFileInput');
          if (fileInput) fileInput.value = '';

          // Refresh auth status
          await fetchCalendarAuthStatus(editingClient.value);

          alert(`Service account uploaded successfully!\nEmail: ${response.data.service_account_email}`);

        } catch (error) {
          console.error("Failed to upload service account:", error);
          const errorMsg = error.response?.data?.detail || "Failed to upload service account.";
          alert(errorMsg);
        } finally {
          uploadingServiceAccount.value = false;
        }
      };

      const revokeCalendarCredentials = async () => {
        if (!editingClient.value) return;

        if (!confirm('Are you sure you want to revoke calendar credentials? This will disconnect calendar access.')) {
          return;
        }

        revokingCredentials.value = true;
        try {
          await axios.delete(
            `/api/clients/${editingClient.value}/calendar/credentials`,
            { headers: { Authorization: `Bearer ${authToken.value}` } }
          );

          // Refresh auth status
          await fetchCalendarAuthStatus(editingClient.value);

          alert('Calendar credentials revoked successfully.');

        } catch (error) {
          console.error("Failed to revoke credentials:", error);
          alert("Failed to revoke credentials. Please try again.");
        } finally {
          revokingCredentials.value = false;
        }
      };

      const deleteCallLogs = async () => {
        if (selectedCallLogs.value.length === 0) return;
        if (
          !confirm(
            `Are you sure you want to delete ${selectedCallLogs.value.length} call log(s)? This action cannot be undone.`,
          )
        )
          return;
        try {
          await Promise.all(
            selectedCallLogs.value.map((id) =>
              axios.delete(`/api/conversation-logs/${id}`),
            ),
          );
          callLogs.value = callLogs.value.filter(
            (log) => !selectedCallLogs.value.includes(log.id),
          );
          addAuditLog(
            "delete",
            `Deleted ${selectedCallLogs.value.length} call log(s)`,
          );
          selectedCallLogs.value = [];
        } catch (error) {
          console.error("Failed to delete call logs:", error);
          alert("Failed to delete call logs");
        }
      };

      const toggleSelectAllCallLogs = () => {
        if (selectAllCallLogs.value) {
          // Deselect all
          selectedCallLogs.value = selectedCallLogs.value.filter(
            (id) => !filteredCallLogs.value.some((log) => log.id === id),
          );
        } else {
          // Select all filtered logs
          const filteredIds = filteredCallLogs.value.map((log) => log.id);
          selectedCallLogs.value = [
            ...new Set([...selectedCallLogs.value, ...filteredIds]),
          ];
        }
      };

      const applyTemplate = () => {
        if (selectedTemplate.value && templates.value[selectedTemplate.value]) {
          const template = templates.value[selectedTemplate.value];
          clientForm.value.initial_greeting = template.initial_greeting;
          clientForm.value.system_prompt = template.system_prompt;
        }
      };

      const toggleClientSelection = (id) => {
        if (selectedClients.value.includes(id)) {
          selectedClients.value = selectedClients.value.filter(
            (clientId) => clientId !== id,
          );
        } else {
          selectedClients.value.push(id);
        }
      };

      const toggleContactSelection = (phone) => {
        if (selectedContacts.value.includes(phone)) {
          selectedContacts.value = selectedContacts.value.filter(
            (p) => p !== phone,
          );
        } else {
          selectedContacts.value.push(phone);
        }
      };

      const toggleBulkSelect = () => {
        if (allSelected.value) {
          // Deselect all filtered clients
          selectedClients.value = selectedClients.value.filter(
            (id) => !filteredClients.value.some((client) => client.id === id),
          );
        } else {
          // Select all filtered clients
          const filteredIds = filteredClients.value.map((client) => client.id);
          selectedClients.value = [
            ...new Set([...selectedClients.value, ...filteredIds]),
          ];
        }
      };

      const bulkDuplicateClients = async () => {
        if (!confirm(`Duplicate ${selectedClients.value.length} clients?`))
          return;
        saving.value = true;
        try {
          await Promise.all(
            selectedClients.value.map((id) => {
              const client = clients.value.find((c) => c.id === id);
              if (client) duplicateClient(client);
            }),
          );
          selectedClients.value = [];
          await loadClients();
        } catch (e) {
          console.error("Bulk duplicate failed:", e);
        } finally {
          saving.value = false;
        }
      };

      const bulkDeleteClients = async () => {
        if (!confirm(`Delete ${selectedClients.value.length} clients?`)) return;
        try {
          await Promise.all(
            selectedClients.value.map((id) => deleteClient(id)),
          );
          selectedClients.value = [];
          await loadClients();
        } catch (e) {
          console.error("Bulk delete failed:", e);
        }
      };

      const toggleSelectAllContacts = () => {
        if (allContactsSelected.value) {
          // Deselect all
          selectedContacts.value = selectedContacts.value.filter(
            (phone) =>
              !filteredContacts.value.some(
                (contact) => contact.phone === phone,
              ),
          );
        } else {
          // Select all filtered contacts
          const filteredPhones = filteredContacts.value.map(
            (contact) => contact.phone,
          );
          selectedContacts.value = [
            ...new Set([...selectedContacts.value, ...filteredPhones]),
          ];
        }
      };

      const bulkDeleteContacts = async () => {
        if (!confirm(`Delete ${selectedContacts.value.length} contacts?`))
          return;
        try {
          await Promise.all(
            selectedContacts.value.map((phone) =>
              axios.delete(`/api/contacts/${encodeURIComponent(phone)}`),
            ),
          );
          // Update local state
          contacts.value = contacts.value.filter(
            (c) => !selectedContacts.value.includes(c.phone),
          );
          selectedContacts.value = [];
        } catch (error) {
          console.error("Bulk delete contacts failed:", error);
          alert("Failed to delete contacts.");
        }
      };

      const exportClients = () => {
        const dataStr = JSON.stringify(clients.value, null, 2);
        const dataUri =
          "data:application/json;charset=utf-8," + encodeURIComponent(dataStr);
        const exportFileDefaultName = "clients_export.json";
        const linkElement = document.createElement("a");
        linkElement.setAttribute("href", dataUri);
        linkElement.setAttribute("download", exportFileDefaultName);
        linkElement.click();
      };

      const handleFileSelect = (event) => {
        importFile.value = event.target.files[0];
      };

      const executeImport = () => {
        if (!importFile.value) return;

        const reader = new FileReader();
        reader.onload = (e) => {
          try {
            const data = JSON.parse(e.target.result);
            const importedClients = Array.isArray(data.clients)
              ? data.clients
              : data;

            // Filter out duplicates by ID
            const existingIds = new Set(clients.value.map((c) => c.id));
            const newUniqueClients = importedClients.filter(
              (c) => !existingIds.has(c.id),
            );

            // Append new clients
            clients.value = [...clients.value, ...newUniqueClients];

            // Save to localStorage
            localStorage.setItem("clients", JSON.stringify(clients.value));

            // Filter and update UI
            filterClients();

            // Alert result
            alert(`Imported ${newUniqueClients.length} new clients.`);

            // Reset importFile
            importFile.value = null;
          } catch (err) {
            alert("Invalid JSON file");
          }
        };
        reader.readAsText(importFile.value);
      };

      const closeModal = () => {
        showCreateModal.value = false;
        showEditModal.value = false;
        editingClient.value = null;

        // Reset Provisioning State
        availableNumbers.value = [];
        searchAreaCode.value = "";
        searchingNumbers.value = false;

        clientForm.value = {
          name: "",
          cell: "",
          calendar_id: "",
          business_timezone: "America/Los_Angeles",
          business_start_hour: 9,
          business_end_hour: 17,
          llm_model: "openai/gpt-4o-mini",
          stt_model: "nova-2-phonecall",
          tts_model: "eleven_flash_v2_5",
          tts_voice_id: "21m00Tcm4TlvDq8ikWAM",
          initial_greeting: "",
          system_prompt: "",
          enabled_tools: [],
          enable_scheduling: false,
          enable_contact_memory: false,
          is_active: true,
        };
        activeClientTab.value = "basic";
        selectedTemplate.value = "";
      };

      const toggleUserMenu = () => {
        showUserMenu.value = !showUserMenu.value;
      };

      const openSettings = () => {
        showUserMenu.value = false;
        showSettingsModal.value = true;
      };

      const openCreateModal = () => {
        showCreateModal.value = true;
        editingClient.value = null;
        activeClientTab.value = "basic";
      };

      const selectClient = (client) => {
        if (!bulkSelectMode.value) {
          editClient(client);
        }
      };

      const testClient = async (client) => {
        try {
          const response = await axios.post(
            "/test_call",
            { client_id: client.id },
            { headers: { Authorization: `Bearer ${authToken.value}` } }
          );
          if (response.data.success) {
            alert(`Test call initiated for ${client.name}`);
          }
        } catch (error) {
          console.error("Test call error:", error);
          alert("Failed to initiate test call");
        }
      };

      const formatMinutes = (seconds) => {
        if (!seconds) return "0 min";
        const minutes = Math.floor(seconds / 60);
        if (minutes < 60) return `${minutes} min`;
        const hours = Math.floor(minutes / 60);
        const remainingMinutes = minutes % 60;
        return remainingMinutes > 0
          ? `${hours}h ${remainingMinutes}m`
          : `${hours}h`;
      };

      const saveUserProfile = async () => {
        try {
          savingProfile.value = true;

          // Validate password fields if changing password
          if (userProfile.value.newPassword) {
            if (!userProfile.value.currentPassword) {
              alert("Please enter your current password");
              return;
            }
            if (userProfile.value.newPassword !== userProfile.value.confirmPassword) {
              alert("New passwords do not match");
              return;
            }
            if (userProfile.value.newPassword.length < 6) {
              alert("New password must be at least 6 characters");
              return;
            }
          }

          // Save display name to localStorage (could be sent to backend later)
          if (userProfile.value.displayName) {
            localStorage.setItem("userDisplayName", userProfile.value.displayName);
          }

          // TODO: Send to backend API to update password
          // For now, just show success message
          if (userProfile.value.newPassword) {
            alert("Profile updated! (Password change will be implemented with backend)");
          } else {
            alert("Profile updated!");
          }

          // Clear password fields
          userProfile.value.currentPassword = "";
          userProfile.value.newPassword = "";
          userProfile.value.confirmPassword = "";

          showUserProfileModal.value = false;
        } catch (error) {
          console.error("Error saving profile:", error);
          alert("Failed to save profile");
        } finally {
          savingProfile.value = false;
        }
      };

      const addAuditLog = (type, action) => {
        const log = {
          id: Date.now(),
          type,
          action,
          timestamp: new Date().toISOString(),
        };
        auditLogs.value.unshift(log);
        if (auditLogs.value.length > 100) {
          auditLogs.value = auditLogs.value.slice(0, 100);
        }
        localStorage.setItem("auditLogs", JSON.stringify(auditLogs.value));
      };

      const formatDate = (dateStr) => {
        if (!dateStr) return "N/A";
        return new Date(dateStr).toLocaleString();
      };

      const formatHour = (hour) => {
        const period = hour >= 12 ? "PM" : "AM";
        const displayHour = hour % 12 || 12;
        return `${displayHour} ${period}`;
      };

      const formatDuration = (seconds) => {
        if (!seconds) return "0s";
        const m = Math.floor(seconds / 60);
        const s = seconds % 60;
        if (m === 0) return `${s}s`;
        return `${m}m ${s}s`;
      };

      const jumpToContact = (phone) => {
        activeTab.value = "contacts";
        // Clear client filter to ensure global search finds the contact
        contactFilterClient.value = "";
        contactSearchQuery.value = phone;
      };

      const formatTimestamp = (timestampStr) => {
        if (!timestampStr) return "";
        try {
          const date = new Date(timestampStr);
          return date.toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
          });
        } catch (e) {
          return "";
        }
      };

      const formatToolName = (toolKey) => {
        const map = {
          get_available_slots: "Avail",
          book_appointment: "Book",
          reschedule_appointment: "Reschedule",
          list_my_appointments: "List Appts",
          save_contact_name: "Save Name",
          cancel_appointment: "Cancel",
        };
        return map[toolKey] || toolKey;
      };

      const getContactName = (phone) => {
        // ROBUST: Check using matchPhones helper to link names even if format differs
        const contact = contacts.value.find((c) => matchPhones(c.phone, phone));
        return contact && contact.name ? contact.name : phone;
      };

      const loadContacts = async () => {
        if (contacts.value.length === 0) isLoading.value = true;
        try {
          const response = await axios.get("/api/contacts");
          contacts.value = response.data.contacts;
        } catch (error) {
          console.error("Failed to load contacts:", error);
        } finally {
          isLoading.value = false;
        }
      };

      const startInlineEdit = (contact) => {
        editingContactPhone.value = contact.phone;
        tempContactName.value = contact.name;
      };

      const cancelInlineEdit = () => {
        editingContactPhone.value = null;
        tempContactName.value = "";
      };

      const saveInlineEdit = async (contact) => {
        try {
          await axios.put(`/api/contacts/${contact.phone}`, {
            name: tempContactName.value,
          });
          await loadContacts(); // Refresh the contacts list
          cancelInlineEdit();
        } catch (error) {
          console.error("Failed to update contact name:", error);
          alert("Failed to update contact name. Please try again.");
        }
      };

      const editContact = (contact) => {
        editingContact.value = { ...contact };
        showEditContactModal.value = true;
      };

      const closeEditContactModal = () => {
        showEditContactModal.value = false;
        editingContact.value = { phone: "", name: "" };
      };

      const closeSettingsModal = () => {
        showSettingsModal.value = false;
      };

      // --- SIMULATOR LOGIC ---
      const openSimulator = (client) => {
        simulatingClient.value = client;
        // Init modal using Bootstrap API
        if (!simulatorModal.value) {
          simulatorModal.value = new bootstrap.Modal(
            document.getElementById("simulatorModal"),
          );
        }
        simulatorModal.value.show();
      };

      const convertFloat32ToInt16 = (buffer) => {
        let l = buffer.length;
        let buf = new Int16Array(l);
        while (l--) {
          // Clamp between -1 and 1 before scaling
          let s = Math.max(-1, Math.min(1, buffer[l]));
          buf[l] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }
        return buf.buffer;
      };

      const startSimulation = async () => {
        if (!simulatingClient.value) return;

        try {
          // 1. Setup Audio Context (Let browser pick sample rate)
          const AudioContext = window.AudioContext || window.webkitAudioContext;
          audioContext.value = new AudioContext();
          let nextStartTime = 0; // GAPLESS AUDIO POINTER

          // RESUME CONTEXT IF SUSPENDED
          if (audioContext.value.state === "suspended") {
            await audioContext.value.resume();
          }
          console.log(
            "Simulator: Connected, Audio Context State:",
            audioContext.value.state,
          );

          // 2. Get Mic Stream
          mediaStream.value = await navigator.mediaDevices.getUserMedia({
            audio: {
              channelCount: 1,
              // Remove sampleRate constraint to satisfy Linux/Mac drivers
              echoCancellation: true,
              noiseSuppression: true,
            },
          });

          // 3. Connect WebSocket
          const proto = window.location.protocol === "https:" ? "wss" : "ws";
          const url = `${proto}://${window.location.host}/ws-simulator/${simulatingClient.value.id}`;

          simulatorSocket.value = new WebSocket(url);
          simulatorSocket.value.binaryType = "arraybuffer";

          simulatorSocket.value.onopen = () => {
            isSimulating.value = true;
            nextStartTime = 0; // Reset pointer on connect

            // 4. Setup Audio Processing (Mic -> WS)
            const source = audioContext.value.createMediaStreamSource(
              mediaStream.value,
            );
            processor.value = audioContext.value.createScriptProcessor(
              4096,
              1,
              1,
            );

            source.connect(processor.value);
            processor.value.connect(audioContext.value.destination);

            processor.value.onaudioprocess = (e) => {
              if (!isSimulating.value) return;

              const inputData = e.inputBuffer.getChannelData(0);
              const sourceRate = audioContext.value.sampleRate;
              const targetRate = 16000;

              if (sourceRate === targetRate) {
                // No resampling needed
                const int16Data = convertFloat32ToInt16(inputData);
                if (
                  simulatorSocket.value &&
                  simulatorSocket.value.readyState === WebSocket.OPEN
                ) {
                  simulatorSocket.value.send(int16Data);
                }
              } else {
                // Manual Downsampling (Linear Interpolation)
                const ratio = sourceRate / targetRate;
                const newLength = Math.floor(inputData.length / ratio);
                const downsampled = new Float32Array(newLength);

                for (let i = 0; i < newLength; i++) {
                  const offset = i * ratio;
                  const index = Math.floor(offset);
                  const decimal = offset - index;
                  const a = inputData[index] || 0;
                  const b = inputData[index + 1] || 0;
                  downsampled[i] = a + (b - a) * decimal;
                }

                const int16Data = convertFloat32ToInt16(downsampled);
                if (
                  simulatorSocket.value &&
                  simulatorSocket.value.readyState === WebSocket.OPEN
                ) {
                  simulatorSocket.value.send(int16Data);
                }
              }
            };
          };

          let firstPacketReceived = false;
          simulatorSocket.value.onmessage = (event) => {
            // 5. Handle Incoming Audio (WS -> Speakers)
            if (event.data instanceof ArrayBuffer) {
              if (!firstPacketReceived) {
                console.log("RX Bytes (First Packet):", event.data.byteLength);
                console.log(
                  "Browser Sample Rate:",
                  audioContext.value.sampleRate,
                );
                firstPacketReceived = true;
              }

              const int16Data = new Int16Array(event.data);
              const float32Data = new Float32Array(int16Data.length);

              for (let i = 0; i < int16Data.length; i++) {
                float32Data[i] = int16Data[i] / 0x7fff;
              }

              // Queue audio
              const buffer = audioContext.value.createBuffer(
                1,
                float32Data.length,
                16000,
              );
              buffer.getChannelData(0).set(float32Data);

              const source = audioContext.value.createBufferSource();
              source.buffer = buffer;
              source.connect(audioContext.value.destination);

              // GAPLESS SCHEDULING LOGIC
              const now = audioContext.value.currentTime;
              // If the queue has run dry (underrun), reset time to 'now' + Jitter Buffer
              if (nextStartTime < now) {
                nextStartTime = now + 0.1; // 100ms jitter buffer
              }

              source.start(nextStartTime);
              nextStartTime += buffer.duration;
            }
          };

          simulatorSocket.value.onclose = (event) => {
            isSimulating.value = false;
            if (event.code === 4002) {
              alert(`Simulation ended: ${event.reason}`);
            }
            stopSimulation();
          };

          simulatorSocket.value.onerror = (error) => {
            console.error("Simulator WS Error:", error);
            stopSimulation();
          };
        } catch (e) {
          console.error("Simulator Init Failed:", e);
          alert("Failed to start simulator. Check microphone permissions.");
          stopSimulation();
        }
      };

      const stopSimulation = () => {
        try {
          if (processor.value) {
            processor.value.disconnect();
            processor.value.onaudioprocess = null;
            processor.value = null;
          }

          if (mediaStream.value) {
            mediaStream.value.getTracks().forEach((track) => track.stop());
            mediaStream.value = null;
          }

          if (audioContext.value) {
            audioContext.value.close();
            audioContext.value = null;
          }

          if (simulatorSocket.value) {
            simulatorSocket.value.close();
            simulatorSocket.value = null;
          }
          simulatingClient.value = null;
        } catch (e) {
          console.error("Error stopping simulation:", e);
        } finally {
          isSimulating.value = false;
          if (simulatorModal.value) {
            simulatorModal.value.hide();
          }
        }
      };

      const openTopUpModal = (client) => {
        selectedTopUpClient.value = client;
        showTopUpModal.value = true;
      };

      const closeTopUpModal = () => {
        showTopUpModal.value = false;
        selectedTopUpClient.value = null;
      };

      const openProvisionModal = (client) => {
        provisioningClient.value = client;
        // Reset search
        availableNumbers.value = [];
        searchAreaCode.value = "";
        showProvisionModal.value = true;
      };

      const closeProvisionModal = () => {
        showProvisionModal.value = false;
        provisioningClient.value = null;
      };

      const confirmNumber = async (client, number) => {
        if (
          !confirm(
            `Claim ${number} for ${client.name}? This will configure the voice webhook.`,
          )
        )
          return;

        try {
          // Call PUT with selected_number to trigger provisioning in backend
          const response = await axios.put(`/api/clients/${client.id}`, {
            selected_number: number,
          });

          // Update local state
          const index = clients.value.findIndex((c) => c.id === client.id);
          if (index !== -1) {
            clients.value[index] = response.data;
          }

          alert("Number provisioned successfully!");
          closeProvisionModal();
          filterClients();
        } catch (error) {
          console.error("Provisioning failed:", error);
          alert(
            "Failed to provision number: " +
              (error.response?.data?.detail || error.message),
          );
        }
      };

      const initiateCheckout = async (packageId) => {
        if (!selectedTopUpClient.value) return;

        try {
          // We use the backend to create the session and redirect to the URL

          const response = await axios.post(
            "/api/billing/create-checkout-session",
            {
              client_id: selectedTopUpClient.value.id,
              package_id: packageId,
            },
          );

          if (response.data.url) {
            window.location.href = response.data.url;
          }
        } catch (error) {
          console.error("Checkout failed:", error);
          alert("Failed to initiate checkout. Please try again.");
        }
      };

      const selectSubscription = async (packageId) => {
        // Wrapper for initiateCheckout but specific to subscription flow
        await initiateCheckout(packageId);
        showSubscriptionModal.value = false;
      };

      const cancelSubscription = async () => {
        const pendingId = localStorage.getItem("pendingPaymentClientId");
        if (pendingId) {
          try {
            await axios.delete(`/api/clients/${pendingId}`);
            clients.value = clients.value.filter((c) => c.id !== pendingId);
            addAuditLog("delete", `Deleted pending client ID: ${pendingId}`);
            filterClients();
          } catch (e) {
            console.warn("Failed to clean up pending client", e);
          }
          localStorage.removeItem("pendingPaymentClientId");
        }
        showSubscriptionModal.value = false;
        selectedTopUpClient.value = null;
      };

      const updateContactName = async () => {
        savingContact.value = true;
        try {
          await axios.put(`/api/contacts/${editingContact.value.phone}`, {
            name: editingContact.value.name,
          });
          await loadContacts(); // Refresh the contacts list
          closeEditContactModal();
        } catch (error) {
          console.error("Failed to update contact name:", error);
          alert("Failed to update contact name. Please try again.");
        } finally {
          savingContact.value = false;
        }
      };

      const deleteContact = async (phone) => {
        if (!confirm("Are you sure you want to delete this contact?")) return;
        try {
          await axios.delete(`/api/contacts/${encodeURIComponent(phone)}`);
          // Update local state instantly
          contacts.value = contacts.value.filter((c) => c.phone !== phone);
        } catch (error) {
          console.error("Failed to delete contact:", error);
          alert("Failed to delete contact.");
        }
      };

      const viewContactHistory = (contact) => {
        logFilterContact.value = contact.phone;
        logFilterClient.value = ""; // Clear client filter to ensure we see the logs
        logSearchQuery.value = contact.phone; // Set search query to phone number
        activeTab.value = "logs";
      };

      const loadLogs = async () => {
        if (callLogs.value.length === 0) isLoading.value = true;
        try {
          const response = await axios.get("/api/conversation-logs");
          callLogs.value = response.data.conversation_logs;
        } catch (error) {
          console.error("Failed to load call logs:", error);
        } finally {
          isLoading.value = false;
        }
      };

      const selectTranscript = (log) => {
        // Pure copy, no manual greeting prepended
        selectedTranscript.value = JSON.parse(JSON.stringify(log));
      };

      const toggleTranscriptExpansion = () => {
        transcriptExpanded.value = !transcriptExpanded.value;
      };

      const toggleSystemPromptExpansion = () => {
        systemPromptExpanded.value = !systemPromptExpanded.value;
      };

      // Theme management functions
      const loadThemes = () => {
        // Load default themes inline to avoid fetch issues
        const defaultThemes = [
          {
            key: "tokyo-night-default",
            name: "Tokyo Night Default",
            data: {
              background: "#1a1b26",
              foreground: "#c0caf5",
              cursor: "#7aa2f7",
              selection: "#283457",
              ansi_colors: {
                black: "#15161E",
                red: "#F77693",
                green: "#9ECE6A",
                yellow: "#E0AF68",
                blue: "#7AA2F7",
                magenta: "#BB9AF7",
                cyan: "#7DCFFF",
                white: "#A9B1D6",
                bright_black: "#414868",
                bright_red: "#F77693",
                bright_green: "#9ECE6A",
                bright_yellow: "#E0AF68",
                bright_blue: "#7AA2F7",
                bright_magenta: "#BB9AF7",
                bright_cyan: "#7DCFFF",
                bright_white: "#C0CAF5",
              },
            },
          },
          {
            key: "tokyo-night-day",
            name: "Tokyo Night Day",
            data: {
              background: "#E2E2E7",
              foreground: "#3760BF",
              cursor: "#2E7DE9",
              selection: "#B7C1E3",
              ansi_colors: {
                black: "#B3B5B9",
                red: "#F52A65",
                green: "#587539",
                yellow: "#8C6C3E",
                blue: "#2E7DE9",
                magenta: "#9854F1",
                cyan: "#007197",
                white: "#6172B0",
                bright_black: "#A1A6C5",
                bright_red: "#F52A65",
                bright_green: "#587539",
                bright_yellow: "#8C6C3E",
                bright_blue: "#2E7DE9",
                bright_magenta: "#9854F1",
                bright_cyan: "#007197",
                bright_white: "#3760BF",
              },
            },
          },
          {
            key: "iceberg-dark",
            name: "Iceberg Dark",
            data: {
              description: "Dark background theme",
              background: "#161821",
              foreground: "#C7C9D1",
              cursor: "#89BFC3",
              selection: "#272C41",
              ansi_colors: {
                black: "#1E212B",
                red: "#E2777A",
                green: "#B6BA89",
                yellow: "#E2A677",
                blue: "#83A5AD",
                magenta: "#9F91A8",
                cyan: "#89BFC3",
                white: "#C7C9D1",
                bright_black: "#6B7089",
                bright_red: "#E98A8A",
                bright_green: "#C0CAF5",
                bright_yellow: "#E9B18A",
                bright_blue: "#91A9C6",
                bright_magenta: "#AD9FAD",
                bright_cyan: "#95C4CC",
                bright_white: "#D2D4DD",
              },
            },
          },
          {
            key: "iceberg-light",
            name: "Iceberg Light",
            data: {
              description: "Light background theme",
              background: "#E8E9EC",
              foreground: "#33374C",
              cursor: "#3F83A6",
              selection: "#CAD0D7",
              ansi_colors: {
                black: "#DCDFE7",
                red: "#CC517A",
                green: "#668E3D",
                yellow: "#C57339",
                blue: "#2D539E",
                magenta: "#7759B5",
                cyan: "#3F83A6",
                white: "#33374C",
                bright_black: "#838A96",
                bright_red: "#CC3768",
                bright_green: "#598030",
                bright_yellow: "#B6662D",
                bright_blue: "#22478E",
                bright_magenta: "#6845AD",
                bright_cyan: "#327698",
                bright_white: "#3D425E",
              },
            },
          },
        ];

        themes.value = defaultThemes;
        applyTheme(currentTheme.value);
      };

      // Helper function to get brightness of a hex color
      const getBrightness = (hexColor) => {
        // Remove # if present
        const color = hexColor.replace("#", "");
        // Convert to RGB
        const r = parseInt(color.substr(0, 2), 16);
        const g = parseInt(color.substr(2, 2), 16);
        const b = parseInt(color.substr(4, 2), 16);
        // Calculate brightness (YIQ formula)
        return (r * 299 + g * 587 + b * 114) / 1000;
      };

      const applyTheme = (themeKey) => {
        const theme = themes.value.find((t) => t.key === themeKey);
        if (!theme) {
          console.warn(`Theme ${themeKey} not found, using default`);
          return;
        }

        const root = document.documentElement;
        const themeData = theme.data;

        // Apply theme colors to CSS custom properties
        root.style.setProperty("--theme-bg", themeData.background || "#1a1b26");
        root.style.setProperty("--theme-fg", themeData.foreground || "#c0caf5");
        root.style.setProperty("--theme-cursor", themeData.cursor || "#7aa2f7");
        root.style.setProperty(
          "--theme-selection",
          themeData.selection || "#283457",
        );

        // Determine if this is a light theme and set appropriate muted text color
        const bgBrightness = getBrightness(themeData.background || "#1a1b26");
        const isLightTheme = bgBrightness > 128;
        const mutedColor = isLightTheme ? "#555" : "#888"; // Light gray for dark themes, dark gray for light themes
        root.style.setProperty("--theme-muted", mutedColor);

        // Apply ANSI colors
        const ansiColors = themeData.ansi_colors;
        if (ansiColors) {
          // Map ANSI colors to our theme variables
          root.style.setProperty(
            "--theme-bg-dark",
            ansiColors.black || "#16161e",
          );
          root.style.setProperty(
            "--theme-bg-mid",
            ansiColors.bright_black || "#2a2a37",
          );
          root.style.setProperty(
            "--theme-card-bg",
            ansiColors.black || "#16161e",
          );
          root.style.setProperty("--theme-blue", ansiColors.blue || "#7dcfff");
          root.style.setProperty(
            "--theme-purple",
            ansiColors.magenta || "#bb9af7",
          );
          root.style.setProperty(
            "--theme-green",
            ansiColors.green || "#9ece6a",
          );
          root.style.setProperty(
            "--theme-yellow",
            ansiColors.yellow || "#e0af68",
          );
          root.style.setProperty(
            "--theme-orange",
            ansiColors.yellow || "#e0af68",
          );
          root.style.setProperty("--theme-red", ansiColors.red || "#f7768e");
          root.style.setProperty("--theme-cyan", ansiColors.cyan || "#7dcfff");
          root.style.setProperty(
            "--theme-comment",
            ansiColors.bright_black || "#565f89",
          );
          root.style.setProperty(
            "--theme-logo-white",
            ansiColors.bright_white || "#ffffff",
          );

          // --- BRIGHT VARIANT MAPPING (Phase 1) ---
          root.style.setProperty(
            "--theme-black-bright",
            ansiColors.bright_black || "#414868",
          );
          root.style.setProperty(
            "--theme-red-bright",
            ansiColors.bright_red || "#f7768e",
          );
          root.style.setProperty(
            "--theme-green-bright",
            ansiColors.bright_green || "#9ece6a",
          );
          root.style.setProperty(
            "--theme-yellow-bright",
            ansiColors.bright_yellow || "#e0af68",
          );
          root.style.setProperty(
            "--theme-blue-bright",
            ansiColors.bright_blue || "#7aa2f7",
          );
          root.style.setProperty(
            "--theme-magenta-bright",
            ansiColors.bright_magenta || "#bb9af7",
          );
          root.style.setProperty(
            "--theme-cyan-bright",
            ansiColors.bright_cyan || "#7dcfff",
          );
          root.style.setProperty(
            "--theme-white-bright",
            ansiColors.bright_white || "#c0caf5",
          );
        }

        // Set Default (Dark Mode) Border Variables
        root.style.setProperty("--theme-border-active", "2px");

        // Set Default (Dark Mode) Tools Variables
        root.style.setProperty("--theme-tools-bg", "transparent");
        root.style.setProperty("--theme-tools-border", "var(--theme-bg-mid)");
        root.style.setProperty("--theme-tools-label", "var(--theme-purple)");

        // Light theme overrides
        if (isLightTheme) {
          // Paper Fix
          root.style.setProperty("--theme-bg-dark", "#ffffff");
          root.style.setProperty("--theme-card-bg", "#ffffff");

          // Ink Fix
          root.style.setProperty("--theme-bg-mid", "#b4b9c9");

          // Dynamic Shadows & Stripes
          root.style.setProperty("--theme-table-stripe", "rgba(0, 0, 0, 0.03)");
          root.style.setProperty(
            "--theme-table-hover",
            "rgba(46, 125, 233, 0.1)",
          );
          root.style.setProperty("--theme-btn-glow", "rgba(0, 0, 0, 0.1)");
          root.style.setProperty("--theme-text-glow", "none");

          // Ambient Backgrounds
          root.style.setProperty(
            "--theme-gradient-1",
            "rgba(55, 96, 191, 0.15)",
          );
          root.style.setProperty(
            "--theme-gradient-2",
            "rgba(120, 117, 213, 0.15)",
          );

          // Border Thickness (Light Mode Override)
          root.style.setProperty("--theme-border-active", "3px");

          // Tools Container (Light Mode Override)
          root.style.setProperty(
            "--theme-tools-bg",
            "rgba(158, 206, 106, 0.15)",
          );
          root.style.setProperty(
            "--theme-tools-border",
            "rgba(88, 117, 57, 0.5)",
          );
          root.style.setProperty("--theme-tools-label", "#3c5220");
        } else {
          // Dark Mode Gradients (Reset)
          root.style.setProperty(
            "--theme-gradient-1",
            "rgba(122, 162, 247, 0.08)",
          );
          root.style.setProperty(
            "--theme-gradient-2",
            "rgba(187, 154, 247, 0.08)",
          );
        }

        currentTheme.value = themeKey;
        localStorage.setItem("currentTheme", themeKey);
      };

      watch(activeTab, (newTab) => {
        if (newTab === "contacts") {
          loadContacts();
        } else if (newTab === "logs") {
          loadLogs();
          if (contacts.value.length === 0) {
            loadContacts();
          }
        }
      });

      watch([searchQuery, filterStatus], () => {
        filterClients();
      });

      // Watch modal state to manage body overflow
      watch(showAuthModal, (isOpen) => {
        if (isOpen) {
          document.body.style.overflow = 'hidden';
          document.body.style.paddingRight = '0px';
        } else {
          document.body.style.overflow = '';
          document.body.style.paddingRight = '';
        }
      });

      // --- Axios Interceptor for 401 ---
      axios.interceptors.response.use(
        (response) => response,
        (error) => {
          if (
            error.response &&
            error.response.status === 401 &&
            authToken.value
          ) {
            alert("Session expired or unauthorized. Please log in again.");
            logout();
          }
          return Promise.reject(error);
        },
      );

      const calculateDuration = (startTime) => {
        if (!startTime) return 0;
        const start = new Date(startTime).getTime();
        const now = new Date().getTime();
        return Math.floor((now - start) / 1000);
      };

      const pollActiveCalls = async () => {
        if (!authToken.value) return;
        try {
          const response = await axios.get("/api/active-calls");
          activeCalls.value = response.data;
        } catch (e) {
          console.error("Active calls poll failed", e);
        }
      };

      onMounted(() => {
        // Check for payment success
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get("payment") === "success") {
          alert("Payment Successful! System refueling...");
          // Strip the param from URL without reloading
          const newUrl =
            window.location.protocol +
            "//" +
            window.location.host +
            window.location.pathname;
          window.history.pushState({ path: newUrl }, "", newUrl);
        } else if (urlParams.get("payment") === "cancelled") {
          alert("Payment Cancelled.");
          const newUrl =
            window.location.protocol +
            "//" +
            window.location.host +
            window.location.pathname;
          window.history.pushState({ path: newUrl }, "", newUrl);
        }

        nextTick(() => {
          const modalEl = document.getElementById("auditLogModal");
          if (modalEl && typeof bootstrap !== "undefined") {
            try {
              auditModal.value = new bootstrap.Modal(modalEl);
            } catch (e) {
              console.error("Failed to initialize audit modal:", e);
            }
          }
        });
        // Load themes asynchronously without blocking app initialization
        setTimeout(() => {
          loadThemes();
          loadTemplates();
        }, 100);

        // Start Polling for Active Calls
        setInterval(pollActiveCalls, 3000);
        setInterval(() => {
          // Force update for timer
          activeCalls.value = [...activeCalls.value];
        }, 1000);

        if (authToken.value) {
          setAuthToken(authToken.value);

          // Clean up pending clients on refresh/cancel
          const pendingId = localStorage.getItem("pendingPaymentClientId");
          if (pendingId) {
            if (urlParams.get("payment") === "success") {
              localStorage.removeItem("pendingPaymentClientId");
              loadClients();
            } else {
              // Silent delete
              axios
                .delete(`/api/clients/${pendingId}`)
                .then(() =>
                  console.log(`Cleaned up pending client ${pendingId}`),
                )
                .catch((e) =>
                  console.warn("Failed to cleanup pending client", e),
                )
                .finally(() => {
                  localStorage.removeItem("pendingPaymentClientId");
                  loadClients();
                });
            }
          } else {
            loadClients();
          }

          pollActiveCalls(); // Initial fetch
          if (activeTab.value === "contacts") {
            loadContacts();
          } else if (activeTab.value === "logs") {
            loadLogs();
          }
        } else {
          // Keep currentView as "landing" for the landing page
          // Don't change it here

          nextTick(() => {
            const modalEl = document.getElementById("auditLogModal");
            if (modalEl && typeof bootstrap !== "undefined") {
              try {
                auditModal.value = new bootstrap.Modal(modalEl);
              } catch (e) {
                console.error("Failed to initialize audit modal:", e);
              }
            }
          });
        }

        // Load user profile data from localStorage
        const savedDisplayName = localStorage.getItem("userDisplayName");
        if (savedDisplayName) {
          userProfile.value.displayName = savedDisplayName;
        }

        // Global fix: blur buttons after click to prevent lingering hover state
        document.addEventListener("click", (e) => {
          if (e.target.closest("button")) {
            setTimeout(() => {
              e.target.closest("button").blur();
            }, 100);
          }
        });
      });

      const hasScheduling = (client) => {
        return (
          client.enabled_tools?.some((tool) =>
            [
              "book_appointment",
              "get_available_slots",
              "reschedule_appointment",
              "list_my_appointments",
            ].includes(tool),
          ) || false
        );
      };

      const hasMemory = (client) => {
        return client.enabled_tools?.includes("save_contact_name") || false;
      };

      const getVoiceName = (voiceId) => {
        if (!voiceId) return "Unknown";
        // Search in both ElevenLabs and Cartesia voices
        const allVoices = [...elevenlabsVoices, ...cartesiaVoices];
        const preset = allVoices.find((v) => v.id === voiceId);
        return preset ? preset.name.split(/[-\(]/)[0].trim() : "Custom Voice";
      };

      const truncateId = (id) => {
        if (!id) return "";
        if (id.length <= 12) return id;
        return id.substring(0, 12) + "...";
      };

      const formatName = (name) => {
        if (!name) return "";
        return name
          .toLowerCase()
          .replace(/(?:^|\s|-)\S/g, (c) => c.toUpperCase())
          .replace(
            /\bMc[a-z]/g,
            (m) => m.substr(0, 2) + m.substr(2).toUpperCase(),
          )
          .replace(
            /\bO'[a-z]/g,
            (m) => m.substr(0, 2) + m.substr(2).toUpperCase(),
          );
      };

      const formatSttModel = (model) => {
        if (!model) return "";
        const type = model.split("-").pop();
        return type.charAt(0).toUpperCase() + type.slice(1);
      };

      const goToRegister = () => {
        currentView.value = "register";
        showAuthModal.value = true;
      };

      const goToLogin = () => {
        currentView.value = "login";
        showAuthModal.value = true;
      };

      const closeAuthModal = () => {
        showAuthModal.value = false;
        authError.value = null;
        authSuccess.value = null;
        // Reset to landing if not authenticated
        if (!authToken.value) {
          currentView.value = "landing";
        }
      };

      return {
        formatName,
        formatSttModel,
        clients,
        filteredClients: paginatedClients,
        selectedClients,
        selectedCallLogs,
        searchQuery,
        filterStatus,
        sortBy,
        currentPage,
        totalPages,
        visiblePages,
        showCreateModal,
        showEditModal,
        showBulkModal,
        showEditContactModal,
        bulkSelectMode,
        openCreateModal,
        selectClient,
        testClient,
        showAuditLog,
        auditModal,
        openAuditLog,
        closeAuditLog,
        showUserMenu,
        toggleUserMenu,
        openSettings,
        saving,
        savingContact,
        selectedTemplate,
        templates,
        auditLogs,
        clientForm,
        editingClient, // Added editingClient export
        editingContact,
        loadContacts,
        editContact,
        closeEditContactModal,
        showSettingsModal,
        closeSettingsModal,
        showUserProfileModal,
        userProfile,
        savingProfile,
        saveUserProfile,
        showTopUpModal,
        selectedTopUpClient,
        openTopUpModal,
        closeTopUpModal,
        showSubscriptionModal,
        selectSubscription,
        cancelSubscription,
        showProvisionModal,
        provisioningClient,
        openProvisionModal,
        closeProvisionModal,
        confirmNumber,
        initiateCheckout,
        updateContactName,
        deleteContact,
        loadClients,
        filterClients,
        sortClients,
        editClient,
        duplicateClient,
        saveClient,
        deleteClient,
        bulkDelete,
        bulkUpdate,
        deleteCallLogs,
        toggleSelectAllCallLogs,
        selectAllCallLogs,
        selectAllIndeterminate,
        applyTemplate,
        exportClients,
        handleFileSelect,
        executeImport,
        importFile,
        toggleBulkSelect,
        toggleClientSelection,
        toggleContactSelection,
        bulkDuplicateClients,
        bulkDeleteClients,
        allSelected,
        closeModal,
        formatDate,
        formatHour,
        formatTimestamp,
        formatToolName,
        formatDuration, // Added formatDuration export
        formatMinutes,
        jumpToContact, // Added jumpToContact export
        activeTab,
        isLoading,
        loading: isLoading,
        contacts,
        selectedContacts,
        callLogs,
        selectedTranscript,
        transcriptExpanded,
        contactSearchQuery,
        contactFilterClient, // <--- EXPORT THIS
        logSearchQuery,
        logFilterClient,
        logFilterContact,
        filteredContacts,
        allContactsSelected,
        contactsSelectIndeterminate,
        editingContactPhone,
        tempContactName,
        startInlineEdit,
        cancelInlineEdit,
        saveInlineEdit,
        toggleSelectAllContacts,
        bulkDeleteContacts,
        filteredCallLogs,
        toggleTranscriptExpansion,
        systemPromptExpanded,
        toggleSystemPromptExpansion,
        getContactName,
        viewContactHistory,
        selectTranscript,
        // Theme exports
        themes,
        currentTheme,
        applyTheme,
        templates,
        voicePresets,
        // Auth exports
        authToken,
        currentUser,
        currentView,
        authForm,
        authError,
        authSuccess,
        login,
        register,
        logout,
        toggleAuthView,
        goToRegister,
        goToLogin,
        closeAuthModal,
        showAuthModal,
        googleLoginInProgress,
        initiateGoogleLogin,
        hasScheduling,
        hasMemory,
        activeClientTab, // Added for Tab UI
        toggleClientStatus, // Added for activate/deactivate
        getVoiceName,
        truncateId,
        activeCalls,
        calculateDuration,
        // Calendar auth exports
        calendarAuthStatus,
        initiatingOAuth,
        serviceAccountFile,
        uploadingServiceAccount,
        revokingCredentials,
        fetchCalendarAuthStatus,
        initiateOAuthFlow,
        handleServiceAccountFileSelect,
        uploadServiceAccount,
        revokeCalendarCredentials,
        // Provisioning exports
        searchNumbers,
        availableNumbers,
        searchAreaCode,
        searchingNumbers,
        // Simulator exports
        openSimulator,
        startSimulation,
        stopSimulation,
        simulatingClient,
        isSimulating,
      };
    },
  }).mount("#app");
}
