using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using JiraSharp.Models;
using Xunit;

public class ProgramTests
{
    private readonly JiraClient _jiraClient;

    public ProgramTests()
    {
        _jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");
    }

    [Fact]
    public async Task SyncTasksAndProjects_WithValidData()
    {
        var projects = await _jiraClient.GetProjectsAsync();
        Assert.NotEmpty(projects);
    }

    [Fact]
    public async Task SyncTasksAndProjects_WithInvalidData()
    {
        var invalidUrl = "https://invalid-url.atlassian.net";
        var jiraClient = new JiraClient(invalidUrl, "your-username", "your-password");
        var projects = await jiraClient.GetProjectsAsync();
        Assert.Empty(projects);
    }

    [Fact]
    public async Task MonitorActivity_WithValidData()
    {
        var notifications = await _jiraClient.GetNotificationsAsync();
        Assert.NotEmpty(notifications);
    }

    [Fact]
    public async Task MonitorActivity_WithInvalidData()
    {
        var invalidUrl = "https://invalid-url.atlassian.net";
        var jiraClient = new JiraClient(invalidUrl, "your-username", "your-password");
        var notifications = await jiraClient.GetNotificationsAsync();
        Assert.Empty(notifications);
    }

    [Fact]
    public async Task AutomateNotifications_WithValidData()
    {
        var notifications = await _jiraClient.GetNotificationsAsync();
        foreach (var notification in notifications)
        {
            if (notification.Type == "issueCreated")
            {
                Console.WriteLine($"Sending notification for issue created: {notification.Subject}");
                // Implementar a lógica para enviar notificações
            }
        }
    }

    [Fact]
    public async Task AutomateNotifications_WithInvalidData()
    {
        var invalidUrl = "https://invalid-url.atlassian.net";
        var jiraClient = new JiraClient(invalidUrl, "your-username", "your-password");
        var notifications = await jiraClient.GetNotificationsAsync();
        foreach (var notification in notifications)
        {
            if (notification.Type == "issueCreated")
            {
                Console.WriteLine($"Sending notification for issue created: {notification.Subject}");
                // Implementar a lógica para enviar notificações
            }
        }
    }
}