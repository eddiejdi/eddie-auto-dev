using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using JiraSharp.Model;
using Xunit;

public class ProgramTests
{
    [Fact]
    public async Task TestGetIssuesAsync_Success()
    {
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        try
        {
            var issues = await jiraClient.GetIssuesAsync(new GetIssuesOptions { Fields = new List<string> { "summary", "status" } });

            Assert.NotEmpty(issues);
            foreach (var issue in issues)
            {
                Console.WriteLine($"Issue: {issue.Key}, Summary: {issue.Fields.Summary}, Status: {issue.Fields.Status.Name}");
            }
        }
        catch (Exception ex)
        {
            throw new Exception("Test failed", ex);
        }
    }

    [Fact]
    public async Task TestGetIssuesAsync_Error()
    {
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        try
        {
            await jiraClient.GetIssuesAsync(new GetIssuesOptions { Fields = new List<string> { "summary", "status" } });
        }
        catch (Exception ex)
        {
            Assert.IsType<ApiException>(ex);
            Console.WriteLine($"Error: {ex.Message}");
        }
    }

    // Add more test cases as needed
}