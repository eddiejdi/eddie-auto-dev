using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.EntityFrameworkCore;

public class JiraClient
{
    private readonly string _url;
    private readonly string _apiKey;

    public JiraClient(string url, string apiKey)
    {
        _url = url;
        _apiKey = apiKey;
    }

    public async Task<List<JiraIssue>> GetIssuesAsync()
    {
        var issues = new List<JiraIssue>();

        using (var client = new HttpClient())
        {
            var response = await client.GetAsync($"{_url}/rest/api/2/search?jql=project={Environment.GetEnvironmentVariable("JIRA_PROJECT")}&fields=key,summary,status");
            response.EnsureSuccessStatusCode();

            var responseBody = await response.Content.ReadAsStringAsync();
            var issuesJson = Newtonsoft.Json.Linq.JObject.Parse(responseBody);

            foreach (var issue in issuesJson["issues"].Children())
            {
                var key = issue["key"].Value<string>();
                var summary = issue["fields"]["summary"].Value<string>();
                var status = issue["fields"]["status"]["name"].Value<string>();

                issues.Add(new JiraIssue { Key = key, Summary = summary, Status = status });
            }
        }

        return issues;
    }
}

public class JiraIssue
{
    public string Key { get; set; }
    public string Summary { get; set; }
    public string Status { get; set; }
}

public class Program
{
    private static async Task Main(string[] args)
    {
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net/rest/api/2", "your-api-key");

        try
        {
            var issues = await jiraClient.GetIssuesAsync();

            foreach (var issue in issues)
            {
                Console.WriteLine($"Issue Key: {issue.Key}, Summary: {issue.Summary}, Status: {issue.Status}");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error fetching issues: {ex.Message}");
        }
    }
}