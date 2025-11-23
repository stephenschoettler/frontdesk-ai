const { createApp, ref, computed, onMounted, watch } = Vue;

console.log("App.js loaded, checking Vue...");

// Check if Vue is loaded
if (typeof Vue === "undefined" || typeof Vue.createApp === "undefined") {
  console.error(
    "Vue.js is not loaded. Please check your internet connection and try refreshing the page.",
  );
  document.getElementById("app").innerHTML =
    '<div class="alert alert-danger">Vue.js failed to load. Please check your internet connection and refresh the page.</div>';
} else {
  Vue.createApp({
    setup() {
      console.log("Vue setup running...");
      const authToken = ref(localStorage.getItem("authToken"));
      const currentUser = ref(null);
      const currentView = ref(authToken.value ? "dashboard" : "login");

      const clients = ref([]);
      const filteredClients = ref([]);
      const selectedClients = ref([]);

      const allSelected = computed(
        () => selectedClients.value.length === filteredClients.value.length,
      );
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
      const showAuditLog = ref(false);
      const systemPromptExpanded = ref(false);
      const saving = ref(false);
      const savingContact = ref(false);
      const selectedTemplate = ref("");

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
      const contacts = ref([]);
      const callLogs = ref([]);
      const selectedTranscript = ref(null);
      const transcriptExpanded = ref(false);

      const contactSearchQuery = ref("");
      const logSearchQuery = ref("");
      const logFilterClient = ref("");

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

      const clientForm = ref({
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
      });

      const editingClient = ref(null);
      const editingContact = ref({
        phone: "",
        name: "",
      });

      const templates = {
        default: {
          initial_greeting:
            "Hi, I'm Front Desk — your friendly AI receptionist. How can I help you today?",
          system_prompt:
            "[System Identity]\nYou are Front Desk, an AI receptionist...",
        },
        spa: {
          initial_greeting: "Welcome to our spa! How may I assist you today?",
          system_prompt:
            "[System Identity]\nYou are the AI receptionist for our spa...",
        },
        restaurant: {
          initial_greeting:
            "Welcome to our restaurant! How can I help with your reservation?",
          system_prompt:
            "[System Identity]\nYou are the AI receptionist for our restaurant...",
        },
      };

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

      const filteredContacts = computed(() => {
        if (!contacts.value) return [];
        return contacts.value.filter((contact) => {
          const search = contactSearchQuery.value.toLowerCase();
          return (
            (contact.name && contact.name.toLowerCase().includes(search)) ||
            contact.phone.toLowerCase().includes(search)
          );
        });
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
          const searchMatch =
            !search ||
            (log.phone && log.phone.toLowerCase().includes(search)) ||
            (log.status && log.status.toLowerCase().includes(search));
          return clientMatch && searchMatch;
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
        } else {
          localStorage.removeItem("authToken");
          delete axios.defaults.headers.common["Authorization"];
          currentUser.value = null;
          currentView.value = "login";
        }
      };

      const login = async () => {
        authError.value = null;
        try {
          const response = await axios.post("/api/auth/login", authForm.value);
          setAuthToken(response.data.access_token);
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
        try {
          const response = await axios.post(
            "/api/auth/register",
            authForm.value,
          );
          alert(response.data.message + ". Please login.");
          toggleAuthView();
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
        authForm.value.password = "";
        currentView.value =
          currentView.value === "login" ? "register" : "login";
      };

      const loadClients = async () => {
        try {
          const response = await axios.get("/api/clients");
          clients.value = response.data.clients.map((c) => ({
            ...c,
            enabled_tools: c.enabled_tools || [],
          }));
          filterClients();
        } catch (error) {
          console.error("Failed to load clients:", error);
        }
      };

      const filterClients = () => {
        let filtered = clients.value.filter((client) => {
          const matchesSearch =
            client.name
              .toLowerCase()
              .includes(searchQuery.value.toLowerCase()) ||
            (client.cell && client.cell.includes(searchQuery.value));
          const matchesStatus =
            !filterStatus.value ||
            (filterStatus.value === "active" && client.cell) ||
            (filterStatus.value === "inactive" && !client.cell);
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

      const editClient = (client) => {
        editingClient.value = client.id;
        clientForm.value = {
          ...client,
          enabled_tools: client.enabled_tools || [],
        };
        showEditModal.value = true;
      };

      const duplicateClient = (client) => {
        const duplicated = { ...client };
        delete duplicated.id;
        delete duplicated.created_at;
        duplicated.name += " (Copy)";
        duplicated.enabled_tools = client.enabled_tools || [];
        editingClient.value = null;
        clientForm.value = duplicated;
        showCreateModal.value = true;
      };

      const saveClient = async () => {
        saving.value = true;
        try {
          let response;
          if (editingClient.value) {
            response = await axios.put(
              `/api/clients/${editingClient.value}`,
              clientForm.value,
            );
            const index = clients.value.findIndex(
              (c) => c.id === editingClient.value,
            );
            clients.value[index] = response.data;
            addAuditLog("update", `Updated client: ${response.data.name}`);
          } else {
            response = await axios.post("/api/clients", clientForm.value);
            clients.value.push(response.data);
            addAuditLog("create", `Created client: ${response.data.name}`);
          }
          closeModal();
          filterClients();
        } catch (error) {
          console.error("Failed to save client:", error);
          alert("Failed to save client");
        } finally {
          saving.value = false;
        }
      };

      const deleteClient = async (id) => {
        if (!confirm("Are you sure you want to delete this client?")) return;
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
        if (selectedTemplate.value && templates[selectedTemplate.value]) {
          const template = templates[selectedTemplate.value];
          clientForm.value.initial_greeting = template.initial_greeting;
          clientForm.value.system_prompt = template.system_prompt;
        }
      };

      const toggleBulkSelect = () => {
        if (selectedClients.value.length === filteredClients.value.length) {
          selectedClients.value = [];
        } else {
          selectedClients.value = filteredClients.value.map((c) => c.id);
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

      const closeModal = () => {
        showCreateModal.value = false;
        showEditModal.value = false;
        editingClient.value = null;
        clientForm.value = {
          name: "",
          cell: "",
          calendar_id: "",
          business_timezone: "America/Los_Angeles",
          business_start_hour: 9,
          business_end_hour: 17,
          llm_model: "openai/gpt-4o-mini",
          tts_voice_id: "21m00Tcm4TlvDq8ikWAM",
          initial_greeting: "",
          system_prompt: "",
          enabled_tools: [
            "get_available_slots",
            "book_appointment",
            "save_contact_name",
          ],
        };
        selectedTemplate.value = "";
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
          save_contact_name: "Save Name",
        };
        return map[toolKey] || toolKey;
      };

      const loadContacts = async () => {
        try {
          const response = await axios.get("/api/contacts");
          contacts.value = response.data.contacts;
        } catch (error) {
          console.error("Failed to load contacts:", error);
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

      const loadLogs = async () => {
        try {
          const response = await axios.get("/api/conversation-logs");
          callLogs.value = response.data.conversation_logs;
        } catch (error) {
          console.error("Failed to load call logs:", error);
        }
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
            "--theme-orange",
            ansiColors.yellow || "#e0af68",
          );
          root.style.setProperty("--theme-red", ansiColors.red || "#f7768e");
          root.style.setProperty(
            "--theme-comment",
            ansiColors.bright_black || "#565f89",
          );
          root.style.setProperty(
            "--theme-logo-white",
            ansiColors.bright_white || "#ffffff",
          );
        }

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
        }

        currentTheme.value = themeKey;
        localStorage.setItem("currentTheme", themeKey);
      };

      watch(activeTab, (newTab) => {
        if (newTab === "contacts") {
          loadContacts();
        } else if (newTab === "logs") {
          loadLogs();
        }
      });

      watch([searchQuery, filterStatus], () => {
        filterClients();
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

      onMounted(() => {
        // Load themes asynchronously without blocking app initialization
        setTimeout(() => {
          loadThemes();
        }, 100);

        if (authToken.value) {
          setAuthToken(authToken.value);
          loadClients();
          if (activeTab.value === "contacts") {
            loadContacts();
          } else if (activeTab.value === "logs") {
            loadLogs();
          }
        } else {
          currentView.value = "login";
        }
      });

      return {
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
        showAuditLog,
        saving,
        savingContact,
        selectedTemplate,
        auditLogs,
        clientForm,
        editingContact,
        loadContacts,
        editContact,
        closeEditContactModal,
        showSettingsModal,
        closeSettingsModal,
        updateContactName,
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
        toggleBulkSelect,
        bulkDuplicateClients,
        bulkDeleteClients,
        allSelected,
        closeModal,
        formatDate,
        formatHour,
        formatTimestamp,
        formatToolName,
        activeTab,
        contacts,
        callLogs,
        selectedTranscript,
        transcriptExpanded,
        contactSearchQuery,
        logSearchQuery,
        logFilterClient,
        filteredContacts,
        filteredCallLogs,
        toggleTranscriptExpansion,
        systemPromptExpanded,
        toggleSystemPromptExpansion,
        // Theme exports
        themes,
        currentTheme,
        applyTheme,
        // Auth exports
        authToken,
        currentUser,
        currentView,
        authForm,
        authError,
        login,
        register,
        logout,
        toggleAuthView,
      };
    },
  }).mount("#app");
}
