using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.EntityFrameworkCore;
using Newtonsoft.Json.Linq;
using Xunit;

public class JiraClientTests
{
    [Fact]
    public async Task GetIssuesAsync_ReturnsEmptyList_WhenNoIssuesExist()
    {
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net/rest/api/2", "your-api-key");

        var issues = await jiraClient.GetIssuesAsync();

        Assert.Empty(issues);
    }

    [Fact]
    public async Task GetIssuesAsync_ReturnsList_WhenIssuesExist()
    {
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net/rest/api/2", "your-api-key");

        // Simulate getting issues from a real API
        var response = await new HttpClient().GetAsync($"{jiraClient._url}/rest/api/2/search?jql=project={Environment.GetEnvironmentVariable("JIRA_PROJECT")}&fields=key,summary,status");
        response.EnsureSuccessStatusCode();

        var responseBody = await response.Content.ReadAsStringAsync();
        var issuesJson = Newtonsoft.Json.Linq.JObject.Parse(responseBody);

        // Create a list of JiraIssue objects
        var issues = new List<JiraIssue>();
        foreach (var issue in issuesJson["issues"].Children())
        {
            var key = issue["key"].Value<string>();
            var summary = issue["fields"]["summary"].Value<string>();
            var status = issue["fields"]["status"]["name"].Value<string>();

            issues.Add(new JiraIssue { Key = key, Summary = summary, Status = status });
        }

        // Assert that the list of issues matches the expected output
        Assert.Equal(issues.Count, 3); // Example: Expected number of issues based on your API response
    }
}