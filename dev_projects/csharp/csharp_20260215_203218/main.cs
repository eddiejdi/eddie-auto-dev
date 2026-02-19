using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;

class Program
{
    static async Task Main(string[] args)
    {
        try
        {
            // Configuração do cliente Jira
            var client = new Client("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");

            // Cria um novo projeto
            var project = await client.Projects.CreateAsync(new ProjectCreateRequest
            {
                Key = "NEWPRJ",
                Name = "New Project"
            });

            Console.WriteLine($"Project created: {project.Key}");

            // Adiciona uma tarefa ao projeto
            var task = await client.Tasks.CreateAsync(project.Id, new TaskCreateRequest
            {
                Summary = "Implement C# Agent with Jira",
                Description = "This task is to integrate C# Agent with Jira for tracking activities."
            });

            Console.WriteLine($"Task created: {task.Key}");

            // Atualiza a tarefa com detalhes adicionais
            await client.Tasks.UpdateAsync(task.Id, new TaskUpdateRequest
            {
                Summary = "Implement C# Agent with Jira",
                Description = "This task is to integrate C# Agent with Jira for tracking activities.",
                Status = TaskStatus.InProgress,
                Assignee = new User { Key = "assignee-key" }
            });

            Console.WriteLine($"Task updated: {task.Key}");

            // Finaliza a tarefa
            await client.Tasks.UpdateAsync(task.Id, new TaskUpdateRequest
            {
                Summary = "Implement C# Agent with Jira",
                Description = "This task is to integrate C# Agent with Jira for tracking activities.",
                Status = TaskStatus.Done,
                Assignee = null
            });

            Console.WriteLine($"Task completed: {task.Key}");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error: {ex.Message}");
        }
    }
}