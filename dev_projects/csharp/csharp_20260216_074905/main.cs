using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.Extensions.DependencyInjection;

namespace JiraTrackingAgent
{
    class Program
    {
        static async Task Main(string[] args)
        {
            var serviceProvider = ConfigureServices();

            await serviceProvider.GetRequiredService<JiraClient>().FetchAndTrackIssues();
        }

        static IServiceProvider ConfigureServices()
        {
            var services = new ServiceCollection();

            services.AddTransient<JiraClient>();
            services.AddTransient<IssueTracker>();

            return services.BuildServiceProvider();
        }
    }

    interface IJiraClient
    {
        Task<List<Issue>> FetchIssuesAsync();
    }

    class JiraClient : IJiraClient
    {
        private readonly HttpClient _httpClient;

        public JiraClient(HttpClient httpClient)
        {
            _httpClient = httpClient;
        }

        public async Task<List<Issue>> FetchIssuesAsync()
        {
            var response = await _httpClient.GetAsync("https://your-jira-instance.atlassian.net/rest/api/2/search?jql=project=YOUR_PROJECT&fields=id,summary,status");
            response.EnsureSuccessStatusCode();

            var responseBody = await response.Content.ReadAsStringAsync();
            var issues = JsonConvert.DeserializeObject<List<Issue>>(responseBody);

            return issues;
        }
    }

    interface IIssueTracker
    {
        Task TrackIssuesAsync(List<Issue> issues);
    }

    class IssueTracker : IIssueTracker
    {
        private readonly HttpClient _httpClient;

        public IssueTracker(HttpClient httpClient)
        {
            _httpClient = httpClient;
        }

        public async Task TrackIssuesAsync(List<Issue> issues)
        {
            foreach (var issue in issues)
            {
                var response = await _httpClient.PutAsync($"https://your-jira-instance.atlassian.net/rest/api/2/issue/{issue.Id}/transitions", new StringContent("{\"transition\":{\"id\":\"YOUR_TRANSITION_ID\"}}"));
                response.EnsureSuccessStatusCode();
            }
        }
    }

    class Issue
    {
        public string Id { get; set; }
        public string Summary { get; set; }
        public string Status { get; set; }
    }
}