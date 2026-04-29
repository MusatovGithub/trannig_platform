import AsyncStorage from "@react-native-async-storage/async-storage";
import { StatusBar } from "expo-status-bar";
import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import {
  ApiClient,
  ClientDashboard,
  CoachClass,
  CoachCustomerDetail,
  CoachDashboard,
  CoachGroup,
  CoachGroupDetail,
  Competition,
  Customer,
  DiaryEntry,
  IssueSubscriptionPayload,
  SubscriptionFormOptions,
  User,
} from "./src/api";

const TOKEN_KEY = "tsunamis_api_token";
const GRADE_OPTIONS = [
  { label: "2", status: "attended_2" },
  { label: "3", status: "attended_3" },
  { label: "4", status: "attended_4" },
  { label: "5", status: "attended_5" },
  { label: "10", status: "attended_10" },
  { label: "Не был", status: "not_attended" },
];
const COACH_MODULES = [
  "Главная",
  "Клиенты",
  "Группы",
  "Занятия",
  "Сотрудники",
  "Достижения",
  "Новости",
  "Соревнования",
  "Испытания",
  "Магазин",
  "Мой профиль",
];
const CLIENT_MODULES = [
  "Главная",
  "Мои достижения",
  "Дневник",
  "Мои соревнования",
  "Испытания",
  "Магазин",
  "Мои покупки",
  "Мой профиль",
];
const CUSTOMER_DETAIL_TABS = [
  "Профиль",
  "Абонементы",
  "Платежи",
  "Документы",
  "Представители",
  "Дневник",
  "Достижения",
  "Соревнования",
  "Испытания",
];

export default function App() {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [competitions, setCompetitions] = useState<Competition[]>([]);
  const [activeCoachModule, setActiveCoachModule] = useState("Главная");
  const [activeClientModule, setActiveClientModule] = useState("Главная");
  const [coachDashboard, setCoachDashboard] = useState<CoachDashboard | null>(
    null,
  );
  const [coachClasses, setCoachClasses] = useState<CoachClass[]>([]);
  const [coachCustomers, setCoachCustomers] = useState<Customer[]>([]);
  const [customerSearch, setCustomerSearch] = useState("");
  const [selectedCustomer, setSelectedCustomer] =
    useState<CoachCustomerDetail | null>(null);
  const [selectedCustomerTab, setSelectedCustomerTab] = useState("Профиль");
  const [subscriptionOptions, setSubscriptionOptions] =
    useState<SubscriptionFormOptions | null>(null);
  const [coachGroups, setCoachGroups] = useState<CoachGroup[]>([]);
  const [selectedGroup, setSelectedGroup] = useState<CoachGroupDetail | null>(
    null,
  );
  const [clientDashboard, setClientDashboard] =
    useState<ClientDashboard | null>(null);
  const [clientDiary, setClientDiary] = useState<DiaryEntry[]>([]);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const api = useMemo(() => new ApiClient(token), [token]);

  useEffect(() => {
    restoreSession();
  }, []);

  async function restoreSession() {
    try {
      const storedToken = await AsyncStorage.getItem(TOKEN_KEY);
      if (!storedToken) {
        return;
      }

      const restoredApi = new ApiClient(storedToken);
      const response = await restoredApi.me();
      setToken(storedToken);
      setUser(response.user);
      await loadWorkspace(restoredApi);
    } catch {
      await AsyncStorage.removeItem(TOKEN_KEY);
    } finally {
      setLoading(false);
    }
  }

  async function loadWorkspace(client = api) {
    const competitionsResponse = await client.competitions();
    setCompetitions(competitionsResponse.competitions);

    try {
      const [coachResponse, classesResponse] = await Promise.all([
          client.coachDashboard(),
          client.coachClasses(),
      ]);
      setCoachDashboard(coachResponse);
      setCoachClasses(classesResponse.classes);
    } catch {
      setCoachDashboard(null);
      setCoachClasses([]);
    }

    try {
      const [dashboardResponse, diaryResponse] = await Promise.all([
        client.clientDashboard(),
        client.clientDiary(),
      ]);
      setClientDashboard(dashboardResponse);
      setClientDiary(diaryResponse.entries);
    } catch {
      setClientDashboard(null);
      setClientDiary([]);
    }
  }

  async function handleLogin() {
    setError("");
    setLoading(true);

    try {
      const response = await api.login(username.trim(), password);
      await AsyncStorage.setItem(TOKEN_KEY, response.token);
      setToken(response.token);
      setUser(response.user);
      api.setToken(response.token);
      await loadWorkspace(api);
    } catch (loginError) {
      setError(
        loginError instanceof Error ? loginError.message : "Не удалось войти",
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleLogout() {
    try {
      await api.logout();
    } finally {
      await AsyncStorage.removeItem(TOKEN_KEY);
      setToken(null);
      setUser(null);
      setCompetitions([]);
      setCoachDashboard(null);
      setCoachClasses([]);
      setCoachCustomers([]);
      setSelectedCustomer(null);
      setSelectedCustomerTab("Профиль");
      setCoachGroups([]);
      setSelectedGroup(null);
      setClientDashboard(null);
      setClientDiary([]);
      setPassword("");
    }
  }

  async function openCoachModule(module: string) {
    setActiveCoachModule(module);
    setError("");

    try {
      if (module === "Клиенты" && coachCustomers.length === 0) {
        const [response, options] = await Promise.all([
          api.customers(),
          api.subscriptionFormOptions(),
        ]);
        setCoachCustomers(response.customers);
        setSubscriptionOptions(options);
      } else if (module === "Клиенты" && !subscriptionOptions) {
        setSubscriptionOptions(await api.subscriptionFormOptions());
      }
      if (module === "Группы" && coachGroups.length === 0) {
        const response = await api.coachGroups();
        setCoachGroups(response.groups);
      }
    } catch (moduleError) {
      setError(
        moduleError instanceof Error
          ? moduleError.message
          : "Не удалось загрузить раздел",
      );
    }
  }

  async function searchCustomers(value: string) {
    setCustomerSearch(value);
    setError("");

    try {
      const response = await api.customers(value);
      setCoachCustomers(response.customers);
      setSelectedCustomer(null);
      setSelectedCustomerTab("Профиль");
    } catch {
      setError("Не удалось найти спортсмена");
    }
  }

  async function handleGrade(attendanceId: number, status: string) {
    setError("");

    try {
      const response = await api.markAttendance(attendanceId, status);
      setCoachClasses((currentClasses) =>
        currentClasses.map((classItem) => ({
          ...classItem,
          attendances: classItem.attendances.map((attendance) =>
            attendance.id === attendanceId
              ? response.attendance
              : attendance,
          ),
        })),
      );
    } catch (gradeError) {
      setError(
        gradeError instanceof Error
          ? gradeError.message
          : "Не удалось сохранить оценку",
      );
    }
  }

  if (loading) {
    return (
      <SafeAreaView style={styles.center}>
        <ActivityIndicator size="large" color="#0f766e" />
      </SafeAreaView>
    );
  }

  if (!user) {
    return (
      <SafeAreaView style={styles.screen}>
        <StatusBar style="dark" />
        <View style={styles.loginPanel}>
          <Text style={styles.title}>Цунамис</Text>
          <Text style={styles.subtitle}>Вход для тренера</Text>

          <TextInput
            autoCapitalize="none"
            inputMode="email"
            onChangeText={setUsername}
            placeholder="Логин"
            style={styles.input}
            value={username}
          />
          <TextInput
            onChangeText={setPassword}
            placeholder="Пароль"
            secureTextEntry
            style={styles.input}
            value={password}
          />

          {error ? <Text style={styles.error}>{error}</Text> : null}

          <Pressable style={styles.primaryButton} onPress={handleLogin}>
            <Text style={styles.primaryButtonText}>Войти</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  const isCoachView = Boolean(coachDashboard || coachClasses.length);

  if (!isCoachView && clientDashboard) {
    return (
      <SafeAreaView style={styles.screen}>
        <StatusBar style="dark" />
        <View style={styles.header}>
          <View>
            <Text style={styles.eyebrow}>Цунамис</Text>
            <Text style={styles.title}>Мой кабинет</Text>
          </View>
          <Pressable style={styles.secondaryButton} onPress={handleLogout}>
            <Text style={styles.secondaryButtonText}>Выйти</Text>
          </Pressable>
        </View>

        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.topNav}
        >
          {CLIENT_MODULES.map((item, index) => (
            <Pressable
              key={item}
              onPress={() => setActiveClientModule(item)}
              style={[
                styles.navItem,
                activeClientModule === item && styles.navItemActive,
              ]}
            >
              <Text
                style={[
                  styles.navItemText,
                  activeClientModule === item && styles.navItemTextActive,
                ]}
              >
                {item}
              </Text>
            </Pressable>
          ))}
        </ScrollView>

        {activeClientModule === "Главная" ? (
          <>
        <View style={styles.statsGrid}>
          <View style={styles.stat}>
            <Text style={styles.statValue}>
              {clientDashboard.distances.week}
            </Text>
            <Text style={styles.statLabel}>км за неделю</Text>
          </View>
          <View style={styles.stat}>
            <Text style={styles.statValue}>
              {clientDashboard.achievements_count}
            </Text>
            <Text style={styles.statLabel}>достижений</Text>
          </View>
          <View style={styles.stat}>
            <Text style={styles.statValue}>
              {clientDashboard.customer.sport_category?.short_name ?? "-"}
            </Text>
            <Text style={styles.statLabel}>разряд</Text>
          </View>
        </View>

        <Text style={styles.sectionTitle}>Испытание</Text>
        <View style={styles.card}>
          <Text style={styles.cardTitle}>
            {clientDashboard.active_challenge?.title ||
              "Активное испытание не выбрано"}
          </Text>
          <Text style={styles.cardMeta}>
            {clientDashboard.active_challenge
              ? `${clientDashboard.active_challenge.progress}/${clientDashboard.active_challenge.target} · ${clientDashboard.active_challenge.reward_points} баллов`
              : "Во вкладке испытаний спортсмен сможет принять вызов и получать дополнительные баллы."}
          </Text>
        </View>

        <Text style={styles.sectionTitle}>Лента</Text>
        {clientDashboard.training_tasks_today.slice(0, 2).map((task) => (
          <View key={`task-${task.class_id}`} style={styles.card}>
            <Text style={styles.cardTitle}>Задание на сегодня</Text>
            <Text style={styles.cardMeta}>
              {task.group?.name || "Группа"} · {task.start?.slice(0, 5) || ""}
            </Text>
            <Text style={styles.cardMeta}>
              Зал: {task.gym_task || "задание пока не внесено"}
            </Text>
            <Text style={styles.cardMeta}>
              Вода: {task.water_task || "задание пока не внесено"}
            </Text>
          </View>
        ))}
        {clientDiary.slice(0, 3).map((entry) => (
          <View key={entry.id} style={styles.card}>
            <Text style={styles.cardTitle}>Последняя оценка: {entry.display_text}</Text>
            <Text style={styles.cardMeta}>
              {entry.date || ""} · {entry.group?.name || "Группа"}
            </Text>
            <Text style={styles.cardMeta}>
              {entry.class_name}
              {entry.comment ? ` · ${entry.comment}` : ""}
            </Text>
          </View>
        ))}

        <Text style={styles.sectionTitle}>Абонемент</Text>
        {clientDashboard.subscriptions.slice(0, 2).map((item) => (
          <View key={item.id} style={styles.card}>
            <Text style={styles.cardTitle}>
              {item.unlimited ? "Безлимит" : `${item.number_classes} занятий`}
            </Text>
            <Text style={styles.cardMeta}>
              Осталось:{" "}
              {item.unlimited
                ? "безлимит"
                : (item.number_classes || 0) - (item.remained || 0)}
              {" · "}до {item.end_date || "без срока"}
            </Text>
          </View>
        ))}

        <Text style={styles.sectionTitle}>Рейтинг</Text>
        <View style={styles.card}>
          <Text style={styles.cardTitle}>В группе</Text>
          <Text style={styles.cardMeta}>
            {clientDashboard.group_ratings.best_group.name || "Группа"} · место{" "}
            {clientDashboard.group_ratings.best_group.place ?? "-"} из{" "}
            {clientDashboard.group_ratings.best_group.total ?? "-"}
          </Text>
        </View>
        <View style={styles.card}>
          <Text style={styles.cardTitle}>В команде</Text>
          <Text style={styles.cardMeta}>
            место {clientDashboard.team.team_place ?? "-"} из{" "}
            {clientDashboard.team.team_total}
          </Text>
        </View>
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Группа недели</Text>
          <Text style={styles.cardMeta}>
            {clientDashboard.company_group_ratings.week_group
              ? `${clientDashboard.company_group_ratings.week_group.name} · средний балл ${clientDashboard.company_group_ratings.week_group.week_average}`
              : "Пока нет оценок за неделю"}
          </Text>
        </View>
        {clientDashboard.company_group_ratings.groups.slice(0, 3).map((group) => (
          <View key={`group-rating-${group.id}`} style={styles.card}>
            <Text style={styles.cardTitle}>
              {group.place}. {group.name}
            </Text>
            <Text style={styles.cardMeta}>
              Средний балл группы: {group.average}
            </Text>
          </View>
        ))}

        <Text style={styles.sectionTitle}>Новости</Text>
        {clientDashboard.news.slice(0, 3).map((item) => (
          <View key={item.id} style={styles.card}>
            <Text style={styles.cardTitle}>{item.title}</Text>
            <Text style={styles.cardMeta}>{item.description}</Text>
          </View>
        ))}

        <Text style={styles.sectionTitle}>Мои старты</Text>
        <FlatList
          contentContainerStyle={styles.list}
          data={competitions}
          keyExtractor={(item) => String(item.id)}
          ListEmptyComponent={
            <Text style={styles.empty}>Соревнований пока нет</Text>
          }
          renderItem={({ item }) => (
            <View style={styles.card}>
              <Text style={styles.cardTitle}>{item.name}</Text>
              <Text style={styles.cardMeta}>{item.location}</Text>
              <Text style={styles.cardMeta}>
                {item.date || "Дата не указана"}
              </Text>
            </View>
          )}
        />
          </>
        ) : (
          <ClientModuleScreen
            activeModule={activeClientModule}
            competitions={competitions}
            dashboard={clientDashboard}
            diary={clientDiary}
            user={user}
          />
        )}
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.screen}>
      <StatusBar style="dark" />
      <View style={styles.header}>
        <View>
          <Text style={styles.eyebrow}>Цунамис</Text>
          <Text style={styles.title}>CRM тренера</Text>
        </View>
        <Pressable style={styles.secondaryButton} onPress={handleLogout}>
          <Text style={styles.secondaryButtonText}>Выйти</Text>
        </Pressable>
      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.topNav}
      >
        {COACH_MODULES.map((item, index) => (
          <Pressable
            key={item}
            onPress={() => openCoachModule(item)}
            style={[
              styles.navItem,
              activeCoachModule === item && styles.navItemActive,
            ]}
          >
            <Text
              style={[
                styles.navItemText,
                activeCoachModule === item && styles.navItemTextActive,
              ]}
            >
              {item}
            </Text>
          </Pressable>
        ))}
      </ScrollView>

      {activeCoachModule === "Главная" ? (
        <>
        <View style={styles.statsGrid}>
          <View style={styles.stat}>
            <Text style={styles.statValue}>
              {coachDashboard?.summary.pending_orders_count ?? "-"}
            </Text>
            <Text style={styles.statLabel}>покупок</Text>
          </View>
          <View style={styles.stat}>
            <Text style={styles.statValue}>
              {coachDashboard?.summary.expired_subscriptions_count ?? "-"}
            </Text>
            <Text style={styles.statLabel}>абонементов истекло</Text>
          </View>
          <View style={styles.stat}>
            <Text style={styles.statValue}>
              {coachDashboard?.summary.unpaid_lessons_count ?? "-"}
            </Text>
            <Text style={styles.statLabel}>не оплачено</Text>
          </View>
          <View style={styles.stat}>
            <Text style={styles.statValue}>
              {coachDashboard?.summary.active_challenges_count ?? "-"}
            </Text>
            <Text style={styles.statLabel}>испытаний</Text>
          </View>
        </View>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <Text style={styles.sectionTitle}>Сегодня</Text>
      {coachDashboard?.today_training_tasks.slice(0, 3).map((task) => (
        <View key={`coach-task-${task.class_id}`} style={styles.card}>
          <Text style={styles.cardTitle}>
            Задание: {task.group?.name || "Группа"}
          </Text>
          <Text style={styles.cardMeta}>
            Зал: {task.gym_task || "нужно внести задание"}
          </Text>
          <Text style={styles.cardMeta}>
            Вода: {task.water_task || "нужно внести задание"}
          </Text>
        </View>
      ))}
      {coachDashboard?.birthdays_today.slice(0, 3).map((customer) => (
        <View key={`birthday-${customer.id}`} style={styles.card}>
          <Text style={styles.cardTitle}>День рождения сегодня</Text>
          <Text style={styles.cardMeta}>{customer.full_name}</Text>
        </View>
      ))}
      {(coachDashboard?.today_classes || coachClasses).slice(0, 3).map((item) => (
        <View key={item.id} style={styles.card}>
          <View style={styles.lessonHeader}>
            <View>
              <Text style={styles.cardTitle}>
                {item.group?.name || item.name || "Занятие"}
              </Text>
              <Text style={styles.cardMeta}>
                {item.start?.slice(0, 5) || "--:--"}
                {item.attendances ? ` · ${item.attendances.length} спортсменов` : ""}
              </Text>
            </View>
          </View>

          {item.attendances?.slice(0, 4).map((attendance) => (
            <View key={attendance.id} style={styles.gradeRow}>
              <View style={styles.gradeStudent}>
                <Text style={styles.studentName}>
                  {attendance.customer.full_name}
                </Text>
                <Text style={styles.cardMeta}>
                  Сейчас: {attendance.display_text}
                </Text>
              </View>
              <View style={styles.gradeActions}>
                {GRADE_OPTIONS.map((option) => (
                  <Pressable
                    key={option.status}
                    onPress={() => handleGrade(attendance.id, option.status)}
                    style={[
                      styles.gradeButton,
                      attendance.status === option.status &&
                        styles.gradeButtonActive,
                      option.status === "not_attended" &&
                        styles.gradeButtonAbsent,
                    ]}
                  >
                    <Text
                      style={[
                        styles.gradeButtonText,
                        attendance.status === option.status &&
                          styles.gradeButtonTextActive,
                      ]}
                    >
                      {option.label}
                    </Text>
                  </Pressable>
                ))}
              </View>
            </View>
          ))}
        </View>
      ))}

      <Text style={styles.sectionTitle}>Требует внимания</Text>
      {coachDashboard?.expired_subscriptions.slice(0, 3).map((item) => (
        <View key={`sub-${item.id}`} style={styles.card}>
          <Text style={styles.cardTitle}>{item.customer.full_name}</Text>
          <Text style={styles.cardMeta}>
            Абонемент закончился {item.end_date || ""}
          </Text>
        </View>
      ))}
      {coachDashboard?.unpaid_lessons.slice(0, 3).map((item) => (
        <View key={`unpaid-${item.customer_id}-${item.group_id}`} style={styles.card}>
          <Text style={styles.cardTitle}>{item.customer_name}</Text>
          <Text style={styles.cardMeta}>
            {item.group_name} · не оплачено занятий: {item.count}
          </Text>
        </View>
      ))}
      {coachDashboard?.pending_orders.slice(0, 3).map((item) => (
        <View key={`order-${item.id}`} style={styles.card}>
          <Text style={styles.cardTitle}>Покупка в магазине</Text>
          <Text style={styles.cardMeta}>
            {item.customer_name} · {item.total_amount} баллов ·{" "}
            {item.status_label}
          </Text>
        </View>
      ))}

      <Text style={styles.sectionTitle}>Ближайшие соревнования</Text>
      <FlatList
        contentContainerStyle={styles.list}
        data={competitions}
        keyExtractor={(item) => String(item.id)}
        ListEmptyComponent={
          <Text style={styles.empty}>Соревнований пока нет</Text>
        }
        renderItem={({ item }) => (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>{item.name}</Text>
            <Text style={styles.cardMeta}>{item.location}</Text>
            <Text style={styles.cardMeta}>{item.date || "Дата не указана"}</Text>
          </View>
        )}
      />
        </>
      ) : (
        <CoachModuleScreen
          activeModule={activeCoachModule}
          classes={coachClasses}
          competitions={competitions}
          customers={coachCustomers}
          customerSearch={customerSearch}
          dashboard={coachDashboard}
          groups={coachGroups}
          onGrade={handleGrade}
          onOpenCustomer={async (customerId) => {
            setSelectedCustomer(await api.coachCustomerDetail(customerId));
            setSelectedCustomerTab("Профиль");
          }}
          onOpenGroup={async (groupId) => {
            setSelectedGroup(await api.coachGroupDetail(groupId));
          }}
          onIssueSubscription={async (customerId, payload) => {
            await api.issueSubscription(customerId, payload);
            setSelectedCustomer(await api.coachCustomerDetail(customerId));
            setSelectedCustomerTab("Абонементы");
          }}
          onSearchCustomers={searchCustomers}
          selectedCustomer={selectedCustomer}
          selectedCustomerTab={selectedCustomerTab}
          setSelectedCustomerTab={setSelectedCustomerTab}
          selectedGroup={selectedGroup}
          subscriptionOptions={subscriptionOptions}
          user={user}
        />
      )}
    </SafeAreaView>
  );
}

function ClientModuleScreen({
  activeModule,
  competitions,
  dashboard,
  diary,
  user,
}: {
  activeModule: string;
  competitions: Competition[];
  dashboard: ClientDashboard;
  diary: DiaryEntry[];
  user: User;
}) {
  if (activeModule === "Дневник") {
    return (
      <ScrollView>
        <Text style={styles.sectionTitle}>Дневник</Text>
        {diary.map((entry) => (
          <View key={entry.id} style={styles.card}>
            <Text style={styles.cardTitle}>{entry.display_text}</Text>
            <Text style={styles.cardMeta}>
              {entry.date || ""} · {entry.group?.name || "Группа"}
            </Text>
            <Text style={styles.cardMeta}>
              {entry.class_name}
              {entry.comment ? ` · ${entry.comment}` : ""}
            </Text>
          </View>
        ))}
      </ScrollView>
    );
  }

  if (activeModule === "Мои соревнования") {
    return (
      <ScrollView>
        <Text style={styles.sectionTitle}>Мои соревнования</Text>
        {competitions.map((competition) => (
          <View key={competition.id} style={styles.card}>
            <Text style={styles.cardTitle}>{competition.name}</Text>
            <Text style={styles.cardMeta}>
              {competition.location} · {competition.date || "дата не указана"}
            </Text>
          </View>
        ))}
      </ScrollView>
    );
  }

  if (activeModule === "Мои достижения") {
    return (
      <ScrollView>
        <Text style={styles.sectionTitle}>Мои достижения</Text>
        <View style={styles.card}>
          <Text style={styles.cardTitle}>
            Получено: {dashboard.achievements_count}
          </Text>
          <Text style={styles.cardMeta}>
            Здесь будет полный список активных и еще не полученных достижений.
          </Text>
        </View>
      </ScrollView>
    );
  }

  if (activeModule === "Испытания") {
    return (
      <ScrollView>
        <Text style={styles.sectionTitle}>Испытания</Text>
        <View style={styles.card}>
          <Text style={styles.cardTitle}>
            {dashboard.active_challenge?.title ||
              "Активное испытание не выбрано"}
          </Text>
          <Text style={styles.cardMeta}>
            Спортсмен выбирает вызов, приложение считает прогресс и начисляет
            баллы после выполнения.
          </Text>
        </View>
      </ScrollView>
    );
  }

  if (activeModule === "Мой профиль") {
    return (
      <ScrollView>
        <Text style={styles.sectionTitle}>Мой профиль</Text>
        <View style={styles.profileAvatar}>
          <Text style={styles.profileAvatarText}>
            {(dashboard.customer.full_name || user.username).slice(0, 1)}
          </Text>
        </View>
        <View style={styles.card}>
          <Text style={styles.cardTitle}>{dashboard.customer.full_name}</Text>
          <Text style={styles.cardMeta}>
            Телефон: {dashboard.customer.phone || "не указан"}
          </Text>
          <Text style={styles.cardMeta}>
            Email: {user.username || "не указан"}
          </Text>
          <Text style={styles.cardMeta}>
            Смена пароля и настройки входа будут в этом разделе.
          </Text>
        </View>
      </ScrollView>
    );
  }

  return (
    <ScrollView>
      <Text style={styles.sectionTitle}>{activeModule}</Text>
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Раздел в работе</Text>
        <Text style={styles.cardMeta}>
          Здесь будет экран раздела с теми же связями, что на сайте.
        </Text>
      </View>
    </ScrollView>
  );
}

function CoachModuleScreen({
  activeModule,
  classes,
  competitions,
  customers,
  customerSearch,
  dashboard,
  groups,
  onGrade,
  onOpenCustomer,
  onOpenGroup,
  onIssueSubscription,
  onSearchCustomers,
  selectedCustomer,
  selectedCustomerTab,
  setSelectedCustomerTab,
  selectedGroup,
  subscriptionOptions,
  user,
}: {
  activeModule: string;
  classes: CoachClass[];
  competitions: Competition[];
  customers: Customer[];
  customerSearch: string;
  dashboard: CoachDashboard | null;
  groups: CoachGroup[];
  onGrade: (attendanceId: number, status: string) => void;
  onOpenCustomer: (customerId: number) => Promise<void>;
  onOpenGroup: (groupId: number) => Promise<void>;
  onIssueSubscription: (
    customerId: number,
    payload: IssueSubscriptionPayload,
  ) => Promise<void>;
  onSearchCustomers: (value: string) => Promise<void>;
  selectedCustomer: CoachCustomerDetail | null;
  selectedCustomerTab: string;
  setSelectedCustomerTab: (tab: string) => void;
  selectedGroup: CoachGroupDetail | null;
  subscriptionOptions: SubscriptionFormOptions | null;
  user: User;
}) {
  if (activeModule === "Клиенты") {
    return (
      <ScrollView>
        <Text style={styles.sectionTitle}>Клиенты</Text>
        <TextInput
          placeholder="Поиск по ФИО или телефону"
          style={styles.input}
          value={customerSearch}
          onChangeText={onSearchCustomers}
        />
        {customers.slice(0, 20).map((customer) => (
          <Pressable
            key={customer.id}
            style={styles.card}
            onPress={() => onOpenCustomer(customer.id)}
          >
            <Text style={styles.cardTitle}>{customer.full_name}</Text>
            <Text style={styles.cardMeta}>
              {(customer.groups || []).map((group) => group.name).join(", ") ||
                "Без группы"}
              {customer.sport_category
                ? ` · ${customer.sport_category.short_name}`
                : ""}
            </Text>
          </Pressable>
        ))}
        {selectedCustomer ? (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>
              {selectedCustomer.customer.full_name}
            </Text>
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              style={styles.innerTabs}
            >
              {CUSTOMER_DETAIL_TABS.map((tab) => (
                <Pressable
                  key={tab}
                  onPress={() => setSelectedCustomerTab(tab)}
                  style={[
                    styles.innerTab,
                    selectedCustomerTab === tab && styles.innerTabActive,
                  ]}
                >
                  <Text
                    style={[
                      styles.innerTabText,
                      selectedCustomerTab === tab &&
                        styles.innerTabTextActive,
                    ]}
                  >
                    {tab}
                  </Text>
                </Pressable>
              ))}
            </ScrollView>
            <CustomerDetailSection
              customerDetail={selectedCustomer}
              onIssueSubscription={onIssueSubscription}
              subscriptionOptions={subscriptionOptions}
              selectedTab={selectedCustomerTab}
            />
          </View>
        ) : null}
      </ScrollView>
    );
  }

  if (activeModule === "Группы") {
    return (
      <ScrollView>
        <Text style={styles.sectionTitle}>Группы</Text>
        {groups.map((group) => (
          <Pressable
            key={group.id}
            style={styles.card}
            onPress={() => onOpenGroup(group.id)}
          >
            <Text style={styles.cardTitle}>{group.name}</Text>
            <Text style={styles.cardMeta}>
              Тренеры:{" "}
              {group.trainers.map((trainer) => trainer.full_name).join(", ") ||
                "не назначены"}
            </Text>
          </Pressable>
        ))}
        {selectedGroup ? (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>{selectedGroup.group.name}</Text>
            <Text style={styles.cardMeta}>
              Спортсменов: {selectedGroup.customers.length} · занятий:{" "}
              {selectedGroup.classes.length}
            </Text>
            <Text style={styles.cardMeta}>
              Цепочки: состав группы, расписание, журнал, абонементы клиентов,
              карточки спортсменов.
            </Text>
          </View>
        ) : null}
      </ScrollView>
    );
  }

  if (activeModule === "Занятия") {
    return (
      <ScrollView>
        <Text style={styles.sectionTitle}>Занятия</Text>
        {classes.map((item) => (
          <View key={item.id} style={styles.card}>
            <Text style={styles.cardTitle}>
              {item.group?.name || item.name || "Занятие"}
            </Text>
            <Text style={styles.cardMeta}>
              {item.date || ""} · {item.start?.slice(0, 5) || "--:--"}
            </Text>
            {item.attendances?.slice(0, 4).map((attendance) => (
              <View key={attendance.id} style={styles.gradeRow}>
                <Text style={styles.studentName}>
                  {attendance.customer.full_name}
                </Text>
                <View style={styles.gradeActions}>
                  {GRADE_OPTIONS.map((option) => (
                    <Pressable
                      key={option.status}
                      onPress={() => onGrade(attendance.id, option.status)}
                      style={[
                        styles.gradeButton,
                        attendance.status === option.status &&
                          styles.gradeButtonActive,
                        option.status === "not_attended" &&
                          styles.gradeButtonAbsent,
                      ]}
                    >
                      <Text
                        style={[
                          styles.gradeButtonText,
                          attendance.status === option.status &&
                            styles.gradeButtonTextActive,
                        ]}
                      >
                        {option.label}
                      </Text>
                    </Pressable>
                  ))}
                </View>
              </View>
            ))}
          </View>
        ))}
      </ScrollView>
    );
  }

  if (activeModule === "Соревнования") {
    return (
      <ScrollView>
        <Text style={styles.sectionTitle}>Соревнования</Text>
        {competitions.map((competition) => (
          <View key={competition.id} style={styles.card}>
            <Text style={styles.cardTitle}>{competition.name}</Text>
            <Text style={styles.cardMeta}>
              {competition.location} · {competition.date || "дата не указана"}
            </Text>
            <Text style={styles.cardMeta}>
              Цепочки: участники, результаты, разряды, импорт протоколов.
            </Text>
          </View>
        ))}
      </ScrollView>
    );
  }

  if (activeModule === "Магазин") {
    return (
      <ScrollView>
        <Text style={styles.sectionTitle}>Магазин</Text>
        {dashboard?.pending_orders.map((order) => (
          <View key={order.id} style={styles.card}>
            <Text style={styles.cardTitle}>Заказ #{order.id}</Text>
            <Text style={styles.cardMeta}>
              {order.customer_name} · {order.total_amount} баллов ·{" "}
              {order.status_label}
            </Text>
          </View>
        ))}
      </ScrollView>
    );
  }

  if (activeModule === "Мой профиль") {
    return (
      <ScrollView>
        <Text style={styles.sectionTitle}>Мой профиль</Text>
        <View style={styles.profileAvatar}>
          <Text style={styles.profileAvatarText}>
            {(user.first_name || user.username).slice(0, 1)}
          </Text>
        </View>
        <View style={styles.card}>
          <Text style={styles.cardTitle}>
            {user.first_name || user.username}
          </Text>
          <Text style={styles.cardMeta}>
            Компания: {user.company?.name || "не указана"}
          </Text>
          <Text style={styles.cardMeta}>
            Смена пароля, аватар и настройки входа будут в этом разделе.
          </Text>
        </View>
      </ScrollView>
    );
  }

  return (
    <ScrollView>
      <Text style={styles.sectionTitle}>{activeModule}</Text>
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Раздел в работе</Text>
        <Text style={styles.cardMeta}>
          Цепочки этого раздела зафиксированы в ТЗ, следующий шаг - поднять
          отдельный API и форму редактирования.
        </Text>
      </View>
    </ScrollView>
  );
}

function CustomerDetailSection({
  customerDetail,
  onIssueSubscription,
  selectedTab,
  subscriptionOptions,
}: {
  customerDetail: CoachCustomerDetail;
  onIssueSubscription: (
    customerId: number,
    payload: IssueSubscriptionPayload,
  ) => Promise<void>;
  selectedTab: string;
  subscriptionOptions: SubscriptionFormOptions | null;
}) {
  const initialGroupId = customerDetail.groups[0]?.id;
  const [groupIds, setGroupIds] = useState<number[]>(
    initialGroupId ? [initialGroupId] : [],
  );
  const [numberClasses, setNumberClasses] = useState("12");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [totalCost, setTotalCost] = useState("");
  const [paymentAmount, setPaymentAmount] = useState("");
  const [cashierId, setCashierId] = useState<number | null>(null);
  const [paymentDate, setPaymentDate] = useState("");
  const [unlimited, setUnlimited] = useState(false);
  const [isFree, setIsFree] = useState(false);
  const [subscriptionError, setSubscriptionError] = useState("");

  async function submitSubscription() {
    setSubscriptionError("");
    try {
      await onIssueSubscription(customerDetail.customer.id, {
        group_ids: groupIds,
        number_classes: unlimited ? null : Number(numberClasses || 0),
        start_date: startDate,
        end_date: endDate,
        unlimited,
        is_free: isFree,
        total_cost: Number(totalCost || 0),
        payment_amount: Number(paymentAmount || 0),
        cashier_id: cashierId,
        payment_date: paymentDate,
      });
      setNumberClasses("12");
      setStartDate("");
      setEndDate("");
      setTotalCost("");
      setPaymentAmount("");
      setCashierId(null);
      setPaymentDate("");
      setUnlimited(false);
      setIsFree(false);
    } catch (error) {
      setSubscriptionError(
        error instanceof Error ? error.message : "Не удалось выдать абонемент",
      );
    }
  }

  if (selectedTab === "Профиль") {
    return (
      <View style={styles.detailBlock}>
        <Text style={styles.cardMeta}>
          Телефон: {customerDetail.customer.phone || "не указан"}
        </Text>
        <Text style={styles.cardMeta}>
          Email: {customerDetail.profile.email || "не указан"}
        </Text>
        <Text style={styles.cardMeta}>
          День рождения: {customerDetail.customer.birth_date || "не указан"}
        </Text>
        <Text style={styles.cardMeta}>
          Группы:{" "}
          {customerDetail.groups.map((group) => group.name).join(", ") ||
            "нет"}
        </Text>
        <Text style={styles.cardMeta}>
          Договор: {customerDetail.profile.contract_number || "не указан"}
        </Text>
      </View>
    );
  }

  if (selectedTab === "Абонементы") {
    return (
      <View style={styles.detailBlock}>
        <View style={styles.formPanel}>
          <Text style={styles.studentName}>Выдать абонемент</Text>
          <Text style={styles.formLabel}>Группы</Text>
          <View style={styles.chipRow}>
            {(subscriptionOptions?.groups || customerDetail.groups).map((group) => {
              const active = groupIds.includes(group.id);
              return (
                <Pressable
                  key={group.id}
                  style={[styles.chip, active && styles.chipActive]}
                  onPress={() => {
                    setGroupIds((current) =>
                      active
                        ? current.filter((id) => id !== group.id)
                        : [...current, group.id],
                    );
                  }}
                >
                  <Text
                    style={[
                      styles.chipText,
                      active && styles.chipTextActive,
                    ]}
                  >
                    {group.name}
                  </Text>
                </Pressable>
              );
            })}
          </View>
          <View style={styles.switchRow}>
            <Pressable
              style={[styles.chip, unlimited && styles.chipActive]}
              onPress={() => setUnlimited((value) => !value)}
            >
              <Text
                style={[styles.chipText, unlimited && styles.chipTextActive]}
              >
                Безлимит
              </Text>
            </Pressable>
            <Pressable
              style={[styles.chip, isFree && styles.chipActive]}
              onPress={() => setIsFree((value) => !value)}
            >
              <Text style={[styles.chipText, isFree && styles.chipTextActive]}>
                Бесплатно
              </Text>
            </Pressable>
          </View>
          {!unlimited ? (
            <TextInput
              keyboardType="number-pad"
              onChangeText={setNumberClasses}
              placeholder="Количество занятий"
              style={styles.input}
              value={numberClasses}
            />
          ) : null}
          <TextInput
            onChangeText={setStartDate}
            placeholder="Дата начала, например 2026-05-01"
            style={styles.input}
            value={startDate}
          />
          <TextInput
            onChangeText={setEndDate}
            placeholder="Дата окончания, например 2026-05-31"
            style={styles.input}
            value={endDate}
          />
          {!isFree ? (
            <>
              <TextInput
                keyboardType="number-pad"
                onChangeText={setTotalCost}
                placeholder="Стоимость абонемента"
                style={styles.input}
                value={totalCost}
              />
              <TextInput
                keyboardType="number-pad"
                onChangeText={setPaymentAmount}
                placeholder="Оплачено сейчас"
                style={styles.input}
                value={paymentAmount}
              />
              <TextInput
                onChangeText={setPaymentDate}
                placeholder="Дата оплаты, например 2026-05-01"
                style={styles.input}
                value={paymentDate}
              />
              <Text style={styles.formLabel}>Касса</Text>
              <View style={styles.chipRow}>
                {(subscriptionOptions?.cashiers || []).map((cashier) => (
                  <Pressable
                    key={cashier.id}
                    style={[
                      styles.chip,
                      cashierId === cashier.id && styles.chipActive,
                    ]}
                    onPress={() => setCashierId(cashier.id)}
                  >
                    <Text
                      style={[
                        styles.chipText,
                        cashierId === cashier.id && styles.chipTextActive,
                      ]}
                    >
                      {cashier.name}
                    </Text>
                  </Pressable>
                ))}
              </View>
            </>
          ) : null}
          {subscriptionError ? (
            <Text style={styles.error}>{subscriptionError}</Text>
          ) : null}
          <Pressable style={styles.primaryButton} onPress={submitSubscription}>
            <Text style={styles.primaryButtonText}>Выдать абонемент</Text>
          </Pressable>
        </View>
        {customerDetail.subscriptions.map((subscription) => (
          <View key={subscription.id} style={styles.subCard}>
            <Text style={styles.studentName}>
              {subscription.unlimited
                ? "Безлимит"
                : `${subscription.number_classes} занятий`}
            </Text>
            <Text style={styles.cardMeta}>
              Осталось: {subscription.classes_left} · до{" "}
              {subscription.end_date || "без срока"} ·{" "}
              {subscription.payment_status}
            </Text>
          </View>
        ))}
      </View>
    );
  }

  if (selectedTab === "Платежи") {
    return (
      <View style={styles.detailBlock}>
        {customerDetail.payments.map((payment) => (
          <View key={payment.id} style={styles.subCard}>
            <Text style={styles.studentName}>
              {payment.amount || 0} руб. · {payment.is_paid ? "оплачено" : "долг"}
            </Text>
            <Text style={styles.cardMeta}>
              {payment.group?.name || "Группа"} · платеж{" "}
              {payment.payment_date || "без даты"} · занятие{" "}
              {payment.lesson_date || "без даты"}
            </Text>
          </View>
        ))}
      </View>
    );
  }

  if (selectedTab === "Документы") {
    return (
      <View style={styles.detailBlock}>
        {customerDetail.documents.length ? (
          customerDetail.documents.map((document) => (
            <View key={document.id} style={styles.subCard}>
              <Text style={styles.studentName}>{document.name}</Text>
              <Text style={styles.cardMeta}>
                {document.file || "файл не загружен"}
              </Text>
            </View>
          ))
        ) : (
          <Text style={styles.cardMeta}>Документы не добавлены</Text>
        )}
      </View>
    );
  }

  if (selectedTab === "Представители") {
    return (
      <View style={styles.detailBlock}>
        {customerDetail.representatives.map((representative) => (
          <View key={representative.id} style={styles.subCard}>
            <Text style={styles.studentName}>
              {representative.full_name || "Представитель"}
            </Text>
            <Text style={styles.cardMeta}>
              {representative.type || "Тип не указан"} ·{" "}
              {representative.phone || "телефон не указан"}
            </Text>
          </View>
        ))}
      </View>
    );
  }

  if (selectedTab === "Дневник") {
    return (
      <View style={styles.detailBlock}>
        {customerDetail.diary.map((entry) => (
          <View key={entry.id} style={styles.subCard}>
            <Text style={styles.studentName}>{entry.display_text}</Text>
            <Text style={styles.cardMeta}>
              {entry.date || ""} · {entry.group?.name || "Группа"} ·{" "}
              {entry.class_name}
            </Text>
            {entry.comment ? (
              <Text style={styles.cardMeta}>{entry.comment}</Text>
            ) : null}
          </View>
        ))}
      </View>
    );
  }

  if (selectedTab === "Достижения") {
    return (
      <View style={styles.detailBlock}>
        {customerDetail.achievements.map((achievement) => (
          <View key={achievement.id} style={styles.subCard}>
            <Text style={styles.studentName}>{achievement.name}</Text>
            <Text style={styles.cardMeta}>
              {achievement.points} баллов · {achievement.description}
            </Text>
          </View>
        ))}
      </View>
    );
  }

  if (selectedTab === "Соревнования") {
    return (
      <View style={styles.detailBlock}>
        {customerDetail.competition_results.map((result) => (
          <View key={result.id} style={styles.subCard}>
            <Text style={styles.studentName}>
              {result.distance} м · {result.discipline || "Дистанция"}
            </Text>
            <Text style={styles.cardMeta}>
              {result.result_time || "без времени"} · место{" "}
              {result.place || "-"} · {result.style_label}
            </Text>
          </View>
        ))}
      </View>
    );
  }

  return (
    <View style={styles.detailBlock}>
      <Text style={styles.studentName}>Испытания спортсмена</Text>
      <Text style={styles.cardMeta}>
        Здесь будут принятые вызовы, прогресс, история выполнения и начисленные
        баллы.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: "#f8fafc",
    paddingHorizontal: 18,
  },
  center: {
    alignItems: "center",
    backgroundColor: "#f8fafc",
    flex: 1,
    justifyContent: "center",
  },
  loginPanel: {
    flex: 1,
    justifyContent: "center",
    gap: 12,
  },
  header: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
    paddingBottom: 16,
    paddingTop: 14,
  },
  eyebrow: {
    color: "#0f766e",
    fontSize: 13,
    fontWeight: "700",
  },
  title: {
    color: "#111827",
    fontSize: 30,
    fontWeight: "800",
  },
  subtitle: {
    color: "#475569",
    fontSize: 17,
    marginBottom: 8,
  },
  input: {
    backgroundColor: "#ffffff",
    borderColor: "#d1d5db",
    borderRadius: 8,
    borderWidth: 1,
    color: "#111827",
    fontSize: 17,
    minHeight: 52,
    paddingHorizontal: 14,
  },
  primaryButton: {
    alignItems: "center",
    backgroundColor: "#0f766e",
    borderRadius: 8,
    minHeight: 52,
    justifyContent: "center",
  },
  primaryButtonText: {
    color: "#ffffff",
    fontSize: 17,
    fontWeight: "800",
  },
  secondaryButton: {
    borderColor: "#0f766e",
    borderRadius: 8,
    borderWidth: 1,
    paddingHorizontal: 14,
    paddingVertical: 9,
  },
  secondaryButtonText: {
    color: "#0f766e",
    fontSize: 15,
    fontWeight: "700",
  },
  topNav: {
    marginBottom: 14,
    marginHorizontal: -18,
    paddingHorizontal: 18,
  },
  navItem: {
    backgroundColor: "#ffffff",
    borderColor: "#d1d5db",
    borderRadius: 8,
    borderWidth: 1,
    marginRight: 8,
    paddingHorizontal: 12,
    paddingVertical: 9,
  },
  navItemActive: {
    backgroundColor: "#0f766e",
    borderColor: "#0f766e",
  },
  navItemText: {
    color: "#334155",
    fontSize: 14,
    fontWeight: "800",
  },
  navItemTextActive: {
    color: "#ffffff",
  },
  error: {
    color: "#b91c1c",
    fontSize: 14,
  },
  list: {
    gap: 10,
    paddingBottom: 28,
  },
  card: {
    backgroundColor: "#ffffff",
    borderColor: "#e5e7eb",
    borderRadius: 8,
    borderWidth: 1,
    padding: 14,
  },
  sectionTitle: {
    color: "#111827",
    fontSize: 18,
    fontWeight: "800",
    marginBottom: 10,
    marginTop: 16,
  },
  statsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  stat: {
    backgroundColor: "#ffffff",
    borderColor: "#e5e7eb",
    borderRadius: 8,
    borderWidth: 1,
    flex: 1,
    minWidth: 150,
    padding: 12,
  },
  statValue: {
    color: "#111827",
    fontSize: 23,
    fontWeight: "900",
  },
  statLabel: {
    color: "#64748b",
    fontSize: 12,
    marginTop: 4,
  },
  profileAvatar: {
    alignItems: "center",
    alignSelf: "flex-start",
    backgroundColor: "#ccfbf1",
    borderRadius: 8,
    height: 76,
    justifyContent: "center",
    marginBottom: 12,
    width: 76,
  },
  profileAvatarText: {
    color: "#0f766e",
    fontSize: 32,
    fontWeight: "900",
  },
  detailBlock: {
    gap: 8,
    marginTop: 12,
  },
  innerTabs: {
    marginHorizontal: -4,
    marginTop: 6,
  },
  innerTab: {
    borderColor: "#d1d5db",
    borderRadius: 8,
    borderWidth: 1,
    marginHorizontal: 4,
    paddingHorizontal: 10,
    paddingVertical: 8,
  },
  innerTabActive: {
    backgroundColor: "#0f766e",
    borderColor: "#0f766e",
  },
  innerTabText: {
    color: "#334155",
    fontSize: 13,
    fontWeight: "800",
  },
  innerTabTextActive: {
    color: "#ffffff",
  },
  subCard: {
    backgroundColor: "#f8fafc",
    borderColor: "#e5e7eb",
    borderRadius: 8,
    borderWidth: 1,
    padding: 10,
  },
  formPanel: {
    backgroundColor: "#ffffff",
    borderColor: "#d1fae5",
    borderRadius: 8,
    borderWidth: 1,
    gap: 10,
    padding: 12,
  },
  formLabel: {
    color: "#334155",
    fontSize: 13,
    fontWeight: "800",
  },
  chipRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  switchRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  chip: {
    borderColor: "#d1d5db",
    borderRadius: 8,
    borderWidth: 1,
    paddingHorizontal: 10,
    paddingVertical: 8,
  },
  chipActive: {
    backgroundColor: "#0f766e",
    borderColor: "#0f766e",
  },
  chipText: {
    color: "#334155",
    fontSize: 13,
    fontWeight: "800",
  },
  chipTextActive: {
    color: "#ffffff",
  },
  moduleGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  module: {
    backgroundColor: "#ccfbf1",
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 11,
  },
  moduleText: {
    color: "#0f766e",
    fontSize: 14,
    fontWeight: "800",
  },
  cardTitle: {
    color: "#111827",
    fontSize: 17,
    fontWeight: "800",
    marginBottom: 6,
  },
  cardMeta: {
    color: "#64748b",
    fontSize: 14,
    lineHeight: 20,
  },
  lessonHeader: {
    borderBottomColor: "#e5e7eb",
    borderBottomWidth: 1,
    marginBottom: 10,
    paddingBottom: 10,
  },
  gradeRow: {
    borderBottomColor: "#f1f5f9",
    borderBottomWidth: 1,
    gap: 10,
    paddingVertical: 10,
  },
  gradeStudent: {
    gap: 2,
  },
  studentName: {
    color: "#111827",
    fontSize: 15,
    fontWeight: "800",
  },
  gradeActions: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 7,
  },
  gradeButton: {
    alignItems: "center",
    borderColor: "#d1d5db",
    borderRadius: 8,
    borderWidth: 1,
    minWidth: 36,
    paddingHorizontal: 9,
    paddingVertical: 7,
  },
  gradeButtonActive: {
    backgroundColor: "#22c55e",
    borderColor: "#22c55e",
  },
  gradeButtonAbsent: {
    borderColor: "#fb923c",
  },
  gradeButtonText: {
    color: "#334155",
    fontSize: 13,
    fontWeight: "900",
  },
  gradeButtonTextActive: {
    color: "#ffffff",
  },
  empty: {
    color: "#64748b",
    fontSize: 16,
    paddingTop: 28,
    textAlign: "center",
  },
});
