using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp;
using Xunit;

namespace CSharpAgentJiraIntegration.Tests
{
    public class ProgramTests
    {
        [Fact]
        public async Task CreateIssueAsync_ShouldCreateTicket()
        {
            // Configuração do JiraSharp
            var jira = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

            // Criar um novo ticket
            var issue = new Issue
            {
                Summary = "Teste C# Agent com Jira",
                Description = "Este é um teste para integrar o C# Agent com Jira.",
                Type = "Bug"
            };

            // Criar a tarefa no Jira
            var createdIssue = await jira.CreateIssueAsync(issue);
            Assert.NotNull(createdIssue.Key, "Ticket não criado");
        }

        [Fact]
        public async Task CreateIssueAsync_ShouldThrowExceptionOnInvalidSummary()
        {
            // Configuração do JiraSharp
            var jira = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

            // Criar um novo ticket com uma descrição vazia
            var issue = new Issue
            {
                Summary = "",
                Description = "Este é um teste para integrar o C# Agent com Jira.",
                Type = "Bug"
            };

            await Assert.ThrowsAsync<ArgumentException>(() => jira.CreateIssueAsync(issue));
        }

        [Fact]
        public async Task UpdateIssueAsync_ShouldUpdateTicket()
        {
            // Configuração do JiraSharp
            var jira = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

            // Criar um novo ticket
            var issue = new Issue
            {
                Summary = "Teste C# Agent com Jira",
                Description = "Este é um teste para integrar o C# Agent com Jira.",
                Type = "Bug"
            };

            var createdIssue = await jira.CreateIssueAsync(issue);
            Assert.NotNull(createdIssue.Key, "Ticket não criado");

            // Atualizar o ticket
            issue.Status = "In Progress";
            await jira.UpdateIssueAsync(createdIssue.Key, issue);

            // Verificar se a atualização foi realizada corretamente
            var updatedIssue = await jira.GetIssueAsync(createdIssue.Key);
            Assert.Equal("In Progress", updatedIssue.Fields.Status.Name, "Status não atualizado");
        }

        [Fact]
        public async Task UpdateIssueAsync_ShouldThrowExceptionOnInvalidStatus()
        {
            // Configuração do JiraSharp
            var jira = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

            // Criar um novo ticket
            var issue = new Issue
            {
                Summary = "Teste C# Agent com Jira",
                Description = "Este é um teste para integrar o C# Agent com Jira.",
                Type = "Bug"
            };

            var createdIssue = await jira.CreateIssueAsync(issue);
            Assert.NotNull(createdIssue.Key, "Ticket não criado");

            // Atualizar o ticket com uma status inválida
            issue.Status = "InvalidStatus";
            await Assert.ThrowsAsync<ArgumentException>(() => jira.UpdateIssueAsync(createdIssue.Key, issue));
        }
    }
}