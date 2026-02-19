using System;
using System.Threading.Tasks;
using JiraSharp.Client;
using JiraSharp.Models;
using Xunit;

public class ProgramTests
{
    [Fact]
    public async Task CreateIssue_Successfully()
    {
        // Configuração do cliente Jira
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Cria um novo issue
        var issue = new Issue
        {
            Summary = "Teste de Integração",
            Description = "Este é um teste para integrar o C# Agent com Jira.",
            Type = new IssueType { Name = "Bug" }
        };

        // Cria a issue no Jira
        await client.Issue.CreateAsync(issue);

        // Verifica se a issue foi criada com sucesso
        Assert.True(issue.Id > 0);
    }

    [Fact]
    public async Task CreateIssue_ThrowsException_WhenSummaryIsNull()
    {
        // Configuração do cliente Jira
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Cria um novo issue com summary nulo
        var issue = new Issue { Summary = null, Description = "Este é um teste para integrar o C# Agent com Jira.", Type = new IssueType { Name = "Bug" } };

        // Tenta criar a issue no Jira e verifica se uma exceção é lançada
        await Assert.ThrowsAsync<ArgumentException>(() => client.Issue.CreateAsync(issue));
    }

    [Fact]
    public async Task CreateIssue_ThrowsException_WhenDescriptionIsNull()
    {
        // Configuração do cliente Jira
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Cria um novo issue com description nulo
        var issue = new Issue { Summary = "Teste de Integração", Description = null, Type = new IssueType { Name = "Bug" } };

        // Tenta criar a issue no Jira e verifica se uma exceção é lançada
        await Assert.ThrowsAsync<ArgumentException>(() => client.Issue.CreateAsync(issue));
    }

    [Fact]
    public async Task CreateIssue_ThrowsException_WhenTypeIsNull()
    {
        // Configuração do cliente Jira
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Cria um novo issue com type nulo
        var issue = new Issue { Summary = "Teste de Integração", Description = "Este é um teste para integrar o C# Agent com Jira.", Type = null };

        // Tenta criar a issue no Jira e verifica se uma exceção é lançada
        await Assert.ThrowsAsync<ArgumentException>(() => client.Issue.CreateAsync(issue));
    }
}