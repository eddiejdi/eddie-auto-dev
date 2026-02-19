import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraService;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.IssueManager;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.project.ProjectManager;
import com.atlassian.plugin.spring.scanner.annotation.ComponentScan;
import com.atlassian.plugin.spring.scanner.annotation.Plugin;

import javax.inject.Inject;
import java.util.List;

@Plugin
@ComponentScan(basePackages = "com.example")
public class JavaAgentTest {

    @Inject
    private JiraService jiraService;

    @Inject
    private IssueManager issueManager;

    @Inject
    private ProjectManager projectManager;

    public void main(String[] args) {
        // Implementar o código aqui
    }

    public void testIntegrateWithJira() {
        List<Project> projects = projectManager.getAllProjects();
        for (Project project : projects) {
            List<Issue> issues = issueManager.getIssues(project.getKey());
            for (Issue issue : issues) {
                System.out.println("Issue: " + issue.getKey() + ", Summary: " + issue.getSummary());
            }
        }
    }

    public void testMonitorActivities() {
        // Implementar o código aqui
    }

    public void testManageTasks() {
        // Implementar o código aqui
    }
}