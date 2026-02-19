using System;
using System.Threading.Tasks;
using JiraSharp.Client;
using Xunit;

public class ProgramTests
{
    [Fact]
    public async Task RegisterTaskAsync_ValidatesTitleAndDescription()
    {
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        await Assert.ThrowsAsync<ArgumentException>(() => await jiraClient.CreateIssue(new Issue { Summary = "", Description = "" }));
        await Assert.ThrowsAsync<ArgumentException>(() => await jiraClient.CreateIssue(new Issue { Summary = null, Description = "" }));
    }

    [Fact]
    public async Task RegisterTaskAsync_SavesTaskToJira()
    {
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        await RegisterTaskAsync("Implementar SCRUM-14", "Integração com Jira para tracking de atividades em C#.");

        // Verificar se a tarefa foi criada no Jira
    }

    [Fact]
    public async Task MonitorTaskProgressAsync_ValidatesIssueKey()
    {
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        await Assert.ThrowsAsync<ArgumentException>(() => await jiraClient.GetIssue(""));
        await Assert.ThrowsAsync<ArgumentException>(() => await jiraClient.GetIssue(null));
    }

    [Fact]
    public async Task MonitorTaskProgressAsync_ReturnsTaskDetails()
    {
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        await RegisterTaskAsync("Implementar SCRUM-14", "Integração com Jira para tracking de atividades em C#.");

        var issueKey = "SCRUM-14";
        var task = await jiraClient.GetIssue(issueKey);

        Assert.NotNull(task);
        Assert.Equal("Implementar SCRUM-14", task.Fields.Summary);
        Assert.Equal("Integração com Jira para tracking de atividades em C#.", task.Fields.Description);
    }
}