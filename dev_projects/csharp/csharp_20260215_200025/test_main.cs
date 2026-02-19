using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using Xunit;

namespace JiraSharp.Tests
{
    public class ProgramTests
    {
        private readonly JiraClient _jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

        [Fact]
        public async Task CreateTaskAsync_ValidData()
        {
            var task = new Task
            {
                Summary = "Implement C# Agent with Jira",
                Description = "This task is to integrate C# Agent with Jira for tracking activities.",
                Priority = 1,
                Assignee = "username"
            };

            await _jiraClient.CreateTaskAsync(task);
        }

        [Fact]
        public async Task CreateTaskAsync_InvalidData()
        {
            var task = new Task
            {
                Summary = "",
                Description = null,
                Priority = -1,
                Assignee = ""
            };

            await Assert.ThrowsAsync<ArgumentException>(() => _jiraClient.CreateTaskAsync(task));
        }

        [Fact]
        public async Task UpdateTaskAsync_ValidData()
        {
            var task = new Task
            {
                Id = 12345, // ID da tarefa existente
                Summary = "Implement C# Agent with Jira (Updated)",
                Description = "This task is to integrate C# Agent with Jira for tracking activities.",
                Priority = 2,
                Assignee = "username"
            };

            await _jiraClient.UpdateTaskAsync(task);
        }

        [Fact]
        public async Task UpdateTaskAsync_InvalidData()
        {
            var task = new Task
            {
                Id = 12345, // ID da tarefa existente
                Summary = "",
                Description = null,
                Priority = -1,
                Assignee = ""
            };

            await Assert.ThrowsAsync<ArgumentException>(() => _jiraClient.UpdateTaskAsync(task));
        }

        [Fact]
        public async Task DeleteTaskAsync_ValidData()
        {
            var task = new Task { Id = 12345 }; // ID da tarefa existente

            await _jiraClient.DeleteTaskAsync(task);
        }

        [Fact]
        public async Task DeleteTaskAsync_InvalidData()
        {
            var task = new Task { Id = -1 }; // ID inválido

            await Assert.ThrowsAsync<ArgumentException>(() => _jiraClient.DeleteTaskAsync(task));
        }
    }
}