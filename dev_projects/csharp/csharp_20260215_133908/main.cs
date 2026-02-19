using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp;

class Program
{
    static async Task Main(string[] args)
    {
        // Configuração do JiraSharp
        var jira = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Cria uma nova tarefa no Jira
        var task = await jira.CreateTaskAsync("New Task", "This is a new task created by the C# Agent.");

        Console.WriteLine($"Task created: {task.Id}");
    }
}