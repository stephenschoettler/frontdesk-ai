const { createApp, ref, computed, onMounted, watch } = Vue;

createApp({
  setup() {
    const authToken = ref(localStorage.getItem("authToken"));
    const currentUser = ref(null);
    const currentView = ref(authToken.value ? "dashboard" : "login");

    const clients = ref([]);
    const filteredClients = ref([]);
    const selectedClients = ref([]);
    const searchQuery = ref("");
    const filterStatus = ref("");
    const sortBy = ref("name");
    const currentPage = ref(1);
    const pageSize = ref(12);
    const showCreateModal = ref(false);
    const showEditModal = ref(false);
    const showBulkModal = ref(false);
    const showAuditLog = ref(false);
    const saving = ref(false);
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

    const contactSearchQuery = ref("");
    const logSearchQuery = ref("");
    const logFilterClient = ref("");

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
      tts_voice_id: "21m00Tcm4TlvDq8ikWAM",
      initial_greeting: "",
      system_prompt: "",
      enabled_tools: [],
    });

    const editingClient = ref(null);

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
        const response = await axios.post("/api/auth/register", authForm.value);
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
      currentView.value = currentView.value === "login" ? "register" : "login";
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
          client.name.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
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
          selectedClients.value.map((id) => axios.delete(`/api/clients/${id}`)),
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

    const applyTemplate = () => {
      if (selectedTemplate.value && templates[selectedTemplate.value]) {
        const template = templates[selectedTemplate.value];
        clientForm.value.initial_greeting = template.initial_greeting;
        clientForm.value.system_prompt = template.system_prompt;
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

    const loadLogs = async () => {
      try {
        const response = await axios.get("/api/conversation-logs");
        callLogs.value = response.data.conversation_logs;
      } catch (error) {
        console.error("Failed to load call logs:", error);
      }
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
      searchQuery,
      filterStatus,
      sortBy,
      currentPage,
      totalPages,
      visiblePages,
      showCreateModal,
      showEditModal,
      showBulkModal,
      showAuditLog,
      saving,
      selectedTemplate,
      auditLogs,
      clientForm,
      loadClients,
      filterClients,
      sortClients,
      editClient,
      duplicateClient,
      saveClient,
      deleteClient,
      bulkDelete,
      bulkUpdate,
      applyTemplate,
      exportClients,
      closeModal,
      formatDate,
      formatHour,
      formatToolName,
      activeTab,
      contacts,
      callLogs,
      selectedTranscript,
      contactSearchQuery,
      logSearchQuery,
      logFilterClient,
      filteredContacts,
      filteredCallLogs,
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
