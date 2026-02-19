using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using JiraSharp.Models;
using NUnit.Framework;

[TestFixture]
public class ProgramTests
{
    [Test]
    public async Task TestCreateIssue()
    {
        // Configuração do cliente Jira
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Cria um novo issue com valores válidos
        var issue = new Issue()
        {
            ProjectKey = "YOUR_PROJECT_KEY",
            Summary = "New Task",
            Description = "This is a new task created by the C# Agent.",
            Priority = new Priority() { Name = "High" },
            Assignee = new User() { Key = "YOUR_USER_KEY" }
        };

        // Adiciona o issue ao Jira
        var addedIssue = await jiraClient.CreateIssueAsync(issue);

        // Verifica se o issue foi criado com sucesso
        Assert.IsNotNull(addedIssue);
        Assert.AreEqual("YOUR_PROJECT_KEY", addedIssue.ProjectKey);
    }

    [Test]
    public async Task TestCreateIssueWithInvalidProjectKey()
    {
        // Configuração do cliente Jira
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Cria um novo issue com um project key inválido
        var issue = new Issue()
        {
            ProjectKey = "INVALID_PROJECT_KEY",
            Summary = "New Task",
            Description = "This is a new task created by the C# Agent.",
            Priority = new Priority() { Name = "High" },
            Assignee = new User() { Key = "YOUR_USER_KEY" }
        };

        // Adiciona o issue ao Jira
        var addedIssue = await jiraClient.CreateIssueAsync(issue);

        // Verifica se o issue foi criado com sucesso
        Assert.IsNull(addedIssue);
    }

    [Test]
    public async Task TestCreateIssueWithEmptySummary()
    {
        // Configuração do cliente Jira
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Cria um novo issue com uma summary vazia
        var issue = new Issue()
        {
            ProjectKey = "YOUR_PROJECT_KEY",
            Summary = "",
            Description = "This is a new task created by the C# Agent.",
            Priority = new Priority() { Name = "High" },
            Assignee = new User() { Key = "YOUR_USER_KEY" }
        };

        // Adiciona o issue ao Jira
        var addedIssue = await jiraClient.CreateIssueAsync(issue);

        // Verifica se o issue foi criado com sucesso
        Assert.IsNull(addedIssue);
    }

    [Test]
    public async Task TestCreateIssueWithNullAssignee()
    {
        // Configuração do cliente Jira
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Cria um novo issue com um assignee nulo
        var issue = new Issue()
        {
            ProjectKey = "YOUR_PROJECT_KEY",
            Summary = "New Task",
            Description = "This is a new task created by the C# Agent.",
            Priority = new Priority() { Name = "High" },
            Assignee = null
        };

        // Adiciona o issue ao Jira
        var addedIssue = await jiraClient.CreateIssueAsync(issue);

        // Verifica se o issue foi criado com sucesso
        Assert.IsNull(addedIssue);
    }
}