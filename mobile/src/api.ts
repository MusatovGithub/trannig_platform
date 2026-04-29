export type User = {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  groups: string[];
  account_type: string;
  permissions: string[];
  mobile_sections: string[];
  company: { id: number; name: string } | null;
};

export type Competition = {
  id: number;
  name: string;
  location: string;
  date: string | null;
  end_date: string | null;
  status: string;
};

export type Customer = {
  id: number;
  full_name: string;
  phone: string | null;
  birth_date?: string | null;
  groups?: { id: number; name: string }[];
  sport_category: { id: number; name: string; short_name: string } | null;
};

export type CompetitionResult = {
  id: number;
  customer: Customer;
  distance: number;
  discipline: string | null;
  style: string | null;
  style_label: string;
  result_time: string | null;
  place: number | null;
  is_disqualified: boolean;
};

export type ClientDashboard = {
  customer: Customer;
  achievements_count: number;
  active_challenge: {
    id: number;
    title: string;
    progress: number;
    target: number;
    reward_points: number;
  } | null;
  trainings_today: {
    id: number;
    name: string;
    group: string;
    start: string;
  }[];
  training_tasks_today: TrainingTask[];
  subscriptions: {
    id: number;
    unlimited: boolean;
    remained: number | null;
    number_classes: number | null;
    days_left: number;
    end_date: string | null;
    percent_used: number;
  }[];
  distances: {
    week: number;
    year: number;
  };
  group_ratings: {
    groups: {
      id: number;
      name: string;
      average: number;
      place: number | null;
      total: number;
    }[];
    best_group: {
      id: number | null;
      name: string;
      avg: number;
      place: number | null;
      total: number | null;
    };
  };
  company_group_ratings: {
    groups: {
      id: number;
      name: string;
      average: number;
      week_average: number;
      place: number;
    }[];
    week_group: {
      id: number;
      name: string;
      average: number;
      week_average: number;
      place: number;
    } | null;
  };
  team: {
    team_avg: number;
    team_place: number | null;
    team_total: number;
  };
  news: {
    id: number;
    title: string;
    description: string;
    created_at: string;
  }[];
};

export type DiaryEntry = {
  id: number;
  date: string | null;
  time: string | null;
  class_name: string;
  group: { id: number; name: string } | null;
  trainer_name: string;
  status: string;
  display_text: string;
  score: number | null;
  comment: string;
};

export type Subscription = {
  id: number;
  groups: { id: number; name: string }[];
  number_classes: number | null;
  used_classes: number;
  classes_left: number | string;
  start_date: string | null;
  end_date: string | null;
  days_left: number;
  unlimited: boolean;
  is_free: boolean;
  is_closed: boolean;
  payment_status: string;
  total_cost: number | null;
};

export type Achievement = {
  id: number;
  name: string;
  description: string;
  image: string;
  tag: string;
  points: number;
  active: boolean;
};

export type CoachDashboard = {
  summary: {
    customers_count: number;
    groups_count: number;
    open_competitions_count: number;
    today_classes_count: number;
    expired_subscriptions_count: number;
    unpaid_lessons_count: number;
    pending_orders_count: number;
    active_challenges_count: number;
  };
  today_classes: CoachClass[];
  today_training_tasks: TrainingTask[];
  birthdays_today: Customer[];
  expired_subscriptions: (Subscription & { customer: Customer })[];
  unpaid_lessons: {
    customer_id: number;
    customer_name: string;
    group_id: number;
    group_name: string;
    count: number;
  }[];
  pending_orders: {
    id: number;
    customer_id: number;
    customer_name: string;
    status: string;
    status_label: string;
    total_amount: number;
    created_at: string | null;
  }[];
  recent_results: {
    id: number;
    customer_name: string;
    competition_name: string;
    distance: number;
    discipline: string | null;
    result_time: string | null;
    place: number | null;
  }[];
};

export type TrainingTask = {
  class_id: number;
  date: string | null;
  start: string | null;
  group: { id: number; name: string } | null;
  gym_task: string;
  water_task: string;
};

export type AttendanceCell = {
  id: number;
  customer: Customer;
  status: string;
  display_text: string;
  comment: string;
  payment_status: string;
  used_subscription_id: number | null;
};

export type CoachClass = {
  id: number;
  name: string;
  date: string | null;
  start: string | null;
  end: string | null;
  group: { id: number; name: string } | null;
  attendances: AttendanceCell[];
};

export type CoachGroup = {
  id: number;
  name: string;
  type_sport: string;
  start_training: string | null;
  end_training: string | null;
  trainers: { id: number; full_name: string }[];
};

export type CoachGroupDetail = {
  group: CoachGroup;
  links: Record<string, string>;
  customers: Customer[];
  classes: CoachClass[];
};

export type CoachCustomerDetail = {
  customer: Customer;
  profile: {
    email: string;
    address: string;
    gender: string;
    contract_number: string;
    contract_type: string;
    start_date: string | null;
  };
  links: Record<string, string>;
  groups: { id: number; name: string }[];
  subscriptions: Subscription[];
  payments: {
    id: number;
    group: { id: number; name: string } | null;
    subscription_id: number | null;
    attendance_id: number | null;
    amount: number | null;
    payment_date: string | null;
    lesson_date: string | null;
    is_paid: boolean;
    is_closed: boolean;
  }[];
  documents: { id: number; name: string; file: string }[];
  representatives: {
    id: number;
    full_name: string;
    phone: string;
    work: string;
    type: string;
  }[];
  diary: DiaryEntry[];
  achievements: Achievement[];
  competition_results: CompetitionResult[];
};

export type SubscriptionFormOptions = {
  groups: CoachGroup[];
  cashiers: { id: number; name: string }[];
  templates: {
    id: number;
    name: string;
    number_classes: number | null;
    unlimited: boolean;
    price: number;
    expired: number;
    is_free: boolean;
  }[];
};

export type IssueSubscriptionPayload = {
  group_ids: number[];
  number_classes: number | null;
  start_date: string;
  end_date: string;
  unlimited: boolean;
  is_free: boolean;
  total_cost: number;
  payment_amount: number;
  cashier_id: number | null;
  payment_date: string;
};

const DEFAULT_API_URL = "https://xn--80aqlcxhu.xn--p1ai/api/v1";

export class ApiClient {
  constructor(
    private token: string | null,
    private baseUrl = DEFAULT_API_URL,
  ) {}

  setToken(token: string | null) {
    this.token = token;
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers = new Headers(options.headers);
    headers.set("Accept", "application/json");

    if (options.body) {
      headers.set("Content-Type", "application/json");
    }

    if (this.token) {
      headers.set("Authorization", `Bearer ${this.token}`);
    }

    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers,
    });
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Ошибка запроса");
    }

    return data as T;
  }

  login(username: string, password: string) {
    return this.request<{ user: User; token: string }>("/auth/login/", {
      method: "POST",
      body: JSON.stringify({
        username,
        password,
        device_name: "iPhone",
      }),
    });
  }

  logout() {
    return this.request<{ success: boolean }>("/auth/logout/", {
      method: "POST",
    });
  }

  me() {
    return this.request<{ user: User }>("/me/");
  }

  competitions() {
    return this.request<{ competitions: Competition[] }>("/competitions/");
  }

  customers(search = "") {
    const query = search ? `?search=${encodeURIComponent(search)}` : "";
    return this.request<{ customers: Customer[] }>(`/customers/${query}`);
  }

  clientDashboard() {
    return this.request<ClientDashboard>("/client/dashboard/");
  }

  clientDiary(params: { date_from?: string; date_to?: string } = {}) {
    const search = new URLSearchParams();
    if (params.date_from) {
      search.set("date_from", params.date_from);
    }
    if (params.date_to) {
      search.set("date_to", params.date_to);
    }
    const query = search.toString() ? `?${search.toString()}` : "";
    return this.request<{ entries: DiaryEntry[] }>(`/client/diary/${query}`);
  }

  clientSubscriptions(active = false) {
    const query = active ? "?active=1" : "";
    return this.request<{ subscriptions: Subscription[] }>(
      `/client/subscriptions/${query}`,
    );
  }

  clientAchievements() {
    return this.request<{ achievements: Achievement[]; active_count: number }>(
      "/client/achievements/",
    );
  }

  clientCompetitionResults() {
    return this.request<{ results: CompetitionResult[] }>(
      "/client/competition-results/",
    );
  }

  coachDashboard() {
    return this.request<CoachDashboard>("/coach/dashboard/");
  }

  coachClasses(date?: string) {
    const query = date ? `?date=${encodeURIComponent(date)}` : "";
    return this.request<{ date: string; classes: CoachClass[] }>(
      `/coach/classes/${query}`,
    );
  }

  coachGroups() {
    return this.request<{ groups: CoachGroup[] }>("/coach/groups/");
  }

  coachGroupDetail(groupId: number) {
    return this.request<CoachGroupDetail>(`/coach/groups/${groupId}/`);
  }

  coachCustomerDetail(customerId: number) {
    return this.request<CoachCustomerDetail>(
      `/coach/customers/${customerId}/`,
    );
  }

  subscriptionFormOptions() {
    return this.request<SubscriptionFormOptions>(
      "/coach/subscriptions/options/",
    );
  }

  issueSubscription(customerId: number, payload: IssueSubscriptionPayload) {
    return this.request<{
      subscription: Subscription;
      payments: CoachCustomerDetail["payments"];
    }>(`/coach/customers/${customerId}/subscriptions/issue/`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  markAttendance(attendanceId: number, status: string, comment = "") {
    return this.request<{ success: boolean; attendance: AttendanceCell }>(
      `/coach/journal/${attendanceId}/mark/`,
      {
        method: "POST",
        body: JSON.stringify({ status, comment }),
      },
    );
  }

  competitionResults(competitionId: number) {
    return this.request<{ results: CompetitionResult[] }>(
      `/competitions/${competitionId}/results/`,
    );
  }
}
