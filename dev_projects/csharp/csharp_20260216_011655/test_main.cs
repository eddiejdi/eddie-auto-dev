using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using JiraSharp.Models;
using Xunit;

namespace YourNamespace.Tests
{
    public class ProgramTests
    {
        private readonly JiraClient _jiraClient;

        public ProgramTests()
        {
            // Configuração do Jira API
            var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");
            this._jiraClient = jiraClient;
        }

        [Fact]
        public async Task CreateIssueAsync_Success()
        {
            // Arrange
            var summary = "Teste C# Agent";
            var description = "Este é um teste para o C# Agent no Jira.";
            var projectKey = "YOUR_PROJECT_KEY";
            var priorityId = 1; // Poderia ser ajustado conforme necessário
            var assigneeId = 2; // Poderia ser ajustado conforme necessário

            // Act
            await CreateIssueAsync(summary, description);

            // Assert
            // Verificar se a issue foi criada corretamente no Jira
        }

        [Fact]
        public async Task CreateIssueAsync_Error()
        {
            // Arrange
            var summary = "Teste C# Agent";
            var description = "Este é um teste para o C# Agent no Jira.";
            var projectKey = "YOUR_PROJECT_KEY";
            var priorityId = 1; // Poderia ser ajustado conforme necessário
            var assigneeId = 2; // Poderia ser ajustado conforme necessário

            // Act
            try
            {
                await CreateIssueAsync(summary, description);
            }
            catch (Exception ex)
            {
                // Assert
                // Verificar se a exceção é da classe esperada
            }
        }

        [Fact]
        public async Task ListIssuesAsync_Success()
        {
            // Arrange
            var issues = await _jiraClient.Issue.GetAllAsync();

            // Act

            // Assert
            // Verificar se a lista de issues foi retornada corretamente
        }

        [Fact]
        public async Task ListIssuesAsync_Error()
        {
            // Arrange

            // Act
            try
            {
                await _jiraClient.Issue.GetAllAsync();
            }
            catch (Exception ex)
            {
                // Assert
                // Verificar se a exceção é da classe esperada
            }
        }

        private async Task CreateIssueAsync(string summary, string description)
        {
            var issue = new Issue
            {
                Summary = summary,
                Description = description,
                ProjectKey = projectKey,
                PriorityId = priorityId,
                AssigneeId = assigneeId,
            };

            var createdIssue = await _jiraClient.Issue.CreateAsync(issue);
            Console.WriteLine($"Created issue: {createdIssue.Key}");
        }
    }
}