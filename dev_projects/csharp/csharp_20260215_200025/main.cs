using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;

class Program
{
    static async Task Main(string[] args)
    {
        // Configuração do cliente Jira
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

        // Função para criar uma nova tarefa no Jira
        async Task CreateTaskAsync()
        {
            var task = new Task
            {
                Summary = "Implement C# Agent with Jira",
                Description = "This task is to integrate C# Agent with Jira for tracking activities.",
                Priority = 1,
                Assignee = "username"
            };

            await jiraClient.CreateTaskAsync(task);
        }

        // Função para atualizar uma tarefa no Jira
        async Task UpdateTaskAsync()
        {
            var task = new Task
            {
                Id = 12345, // ID da tarefa existente
                Summary = "Implement C# Agent with Jira (Updated)",
                Description = "This task is to integrate C# Agent with Jira for tracking activities.",
                Priority = 2,
                Assignee = "username"
            };

            await jiraClient.UpdateTaskAsync(task);
        }

        // Função para deletar uma tarefa no Jira
        async Task DeleteTaskAsync()
        {
            var task = new Task { Id = 12345 }; // ID da tarefa existente

            await jiraClient.DeleteTaskAsync(task);
        }

        try
        {
            Console.WriteLine("Creating a new task...");
            await CreateTaskAsync();

            Console.WriteLine("Updating the task...");
            await UpdateTaskAsync();

            Console.WriteLine("Deleting the task...");
            await DeleteTaskAsync();
        }
        catch (Exception ex)
        {
            Console.WriteLine($"An error occurred: {ex.Message}");
        }
    }
}