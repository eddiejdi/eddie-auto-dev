using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using JiraSharp.Models;

class Program
{
    static async Task Main(string[] args)
    {
        // Inicialize o cliente Jira
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Crie um novo projeto no Jira
        var project = await client.Projects.Create(new Project
        {
            Key = "NEWPROJECT",
            Name = "New Project",
            Description = "This is a new project for tracking activities."
        });

        Console.WriteLine($"Project created: {project.Key}");

        // Crie um novo issue no Jira
        var issue = await client.Issues.Create(new Issue
        {
            Key = "NEWISSUE",
            Summary = "New Issue",
            Description = "This is a new issue for tracking activities.",
            ProjectId = project.Id,
            AssigneeId = 1 // Replace with the ID of the user you want to assign the issue to
        });

        Console.WriteLine($"Issue created: {issue.Key}");

        // Crie uma tarefa no Jira
        var task = await client.Tasks.Create(new Task
        {
            Key = "NEWTASK",
            Summary = "New Task",
            Description = "This is a new task for tracking activities.",
            IssueId = issue.Id,
            AssigneeId = 1 // Replace with the ID of the user you want to assign the task to
        });

        Console.WriteLine($"Task created: {task.Key}");

        // Crie uma atividade no Jira
        var activity = await client.Activities.Create(new Activity
        {
            Key = "NEWACTIVITY",
            Summary = "New Activity",
            Description = "This is a new activity for tracking activities.",
            TaskId = task.Id,
            StatusId = 1 // Replace with the ID of the status you want to assign the activity to
        });

        Console.WriteLine($"Activity created: {activity.Key}");
    }
}