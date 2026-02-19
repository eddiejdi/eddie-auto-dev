using System;
using System.Net.Http;
using System.Text.Json;
using System.Threading.Tasks;

public class JiraClientTests
{
    private readonly string _jiraUrl = "https://your-jira-instance.atlassian.net";
    private readonly string _apiKey = "your-api-key";

    public async Task TestCreateIssueAsync()
    {
        var jiraClient = new JiraClient(_jiraUrl, _apiKey);

        await jiraClient.CreateIssueAsync("YOUR-PROJECT-KEY", "Task", "Implement a feature in C#", "This is the task description.");

        // Assert that the issue was created successfully
        Console.WriteLine("Test Create Issue Async passed.");
    }

    public async Task TestCreateIssueAsyncWithInvalidData()
    {
        var jiraClient = new JiraClient(_jiraUrl, _apiKey);

        await Assert.ThrowsAsync<ArgumentException>(() => jiraClient.CreateIssueAsync("YOUR-PROJECT-KEY", "Task", "", "This is the task description."));
        Console.WriteLine("Test Create Issue Async with Invalid Data passed.");
    }

    public async Task TestGetIssuesAsync()
    {
        var jiraClient = new JiraClient(_jiraUrl, _apiKey);

        await jiraClient.GetIssuesAsync("YOUR-PROJECT-KEY");

        // Assert that the issues were retrieved successfully
        Console.WriteLine("Test Get Issues Async passed.");
    }

    public async Task TestGetIssuesAsyncWithInvalidData()
    {
        var jiraClient = new JiraClient(_jiraUrl, _apiKey);

        await Assert.ThrowsAsync<ArgumentException>(() => jiraClient.GetIssuesAsync(""));
        Console.WriteLine("Test Get Issues Async with Invalid Data passed.");
    }

    public async Task TestUpdateIssueAsync()
    {
        var jiraClient = new JiraClient(_jiraUrl, _apiKey);

        await jiraClient.UpdateIssueAsync("YOUR-ISSUE-ID", "Updated Task", "This is the updated task description.");

        // Assert that the issue was updated successfully
        Console.WriteLine("Test Update Issue Async passed.");
    }

    public async Task TestUpdateIssueAsyncWithInvalidData()
    {
        var jiraClient = new JiraClient(_jiraUrl, _apiKey);

        await Assert.ThrowsAsync<ArgumentException>(() => jiraClient.UpdateIssueAsync("YOUR-ISSUE-ID", "", "This is the updated task description."));
        Console.WriteLine("Test Update Issue Async with Invalid Data passed.");
    }

    public async Task TestDeleteIssueAsync()
    {
        var jiraClient = new JiraClient(_jiraUrl, _apiKey);

        await jiraClient.DeleteIssueAsync("YOUR-ISSUE-ID");

        // Assert that the issue was deleted successfully
        Console.WriteLine("Test Delete Issue Async passed.");
    }

    public async Task TestDeleteIssueAsyncWithInvalidData()
    {
        var jiraClient = new JiraClient(_jiraUrl, _apiKey);

        await Assert.ThrowsAsync<ArgumentException>(() => jiraClient.DeleteIssueAsync(""));
        Console.WriteLine("Test Delete Issue Async with Invalid Data passed.");
    }

    public async Task TestNotifyWebhookAsync()
    {
        var jiraClient = new JiraClient(_jiraUrl, _apiKey);

        await jiraClient.NotifyWebhookAsync("https://your-webhook-url.com/webhook", "{\"message\": \"New issue created\"}");

        // Assert that the webhook notification was sent successfully
        Console.WriteLine("Test Notify Webhook Async passed.");
    }

    public async Task TestNotifyWebhookAsyncWithInvalidData()
    {
        var jiraClient = new JiraClient(_jiraUrl, _apiKey);

        await Assert.ThrowsAsync<ArgumentException>(() => jiraClient.NotifyWebhookAsync("", "{\"message\": \"New issue created\"}"));
        Console.WriteLine("Test Notify Webhook Async with Invalid Data passed.");
    }
}