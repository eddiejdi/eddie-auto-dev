import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.issue.Issue;

public class JavaAgentJiraIntegration {

    public static void main(String[] args) {
        // Implementar a lógica para integrar o Java Agent com Jira
        // ...
    }

    private static void createIssue(Jira jira, Project project, String issueType, String summary) throws Exception {
        IssueServiceContext context = new IssueServiceContext();
        context.setProject(project);
        context.setUser(jira.getAuthentication().getUser());
        context.setComponent(null);

        Issue issue = jira.createIssue(context, issueType, summary);
        System.out.println("Created issue: " + issue.getId());
    }

    private static void updateIssue(Jira jira, Project project, String issueId, String summary) throws Exception {
        IssueServiceContext context = new IssueServiceContext();
        context.setProject(project);
        context.setUser(jira.getAuthentication().getUser());

        Issue issue = jira.updateIssue(context, issueId, summary);
        System.out.println("Updated issue: " + issue.getId());
    }

    private static void deleteIssue(Jira jira, Project project, String issueId) throws Exception {
        IssueServiceContext context = new IssueServiceContext();
        context.setProject(project);
        context.setUser(jira.getAuthentication().getUser());

        jira.deleteIssue(context, issueId);
        System.out.println("Deleted issue: " + issueId);
    }
}