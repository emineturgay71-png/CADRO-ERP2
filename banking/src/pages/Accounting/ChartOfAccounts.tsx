import _ from "@/lib/translate"
import { useState } from "react"
import { useFrappeGetDocList } from "frappe-react-sdk"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Loader2Icon, SearchIcon } from "lucide-react"

type AccountRow = {
    name: string
    account_name: string
    account_number?: string | null
    account_type: string
    root_type: string
    report_type: string
    is_group: 0 | 1
    disabled: 0 | 1
    account_currency: string
    parent_account?: string | null
    company: string
}

const ChartOfAccounts = () => {
    const [search, setSearch] = useState("")
    const [rootType, setRootType] = useState<string | "">("")
    const { data, isLoading, error } = useFrappeGetDocList<AccountRow>("Account", {
        fields: ["name", "account_name", "account_number", "account_type", "root_type", "report_type", "is_group", "disabled", "account_currency", "parent_account", "company"],
        orderBy: { field: "lft", order: "asc" },
        limit: 500,
    })

    const filtered = data
        ? data
              .filter(r => (search === "" || r.account_name.toLowerCase().includes(search.toLowerCase()) || (r.account_number || "").includes(search)))
              .filter(r => rootType === "" || r.root_type === rootType)
        : []

    if (error) return <div className="p-4 text-destructive">{_("Failed to load chart of accounts.")}</div>

    return (
        <div className="flex flex-col gap-4">
            <div className="flex items-center gap-4">
                <div className="relative flex-1 max-w-sm">
                    <SearchIcon className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
                    <Input
                        className="pl-8"
                        placeholder={_("Search accounts...")}
                        value={search}
                        onChange={e => setSearch(e.target.value)}
                    />
                </div>
                <Select value={rootType} onValueChange={setRootType}>
                    <SelectTrigger className="w-48">
                        <SelectValue placeholder={_("All Types")} />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="">{_("All Types")}</SelectItem>
                        <SelectItem value="Asset">{_("Asset")}</SelectItem>
                        <SelectItem value="Liability">{_("Liability")}</SelectItem>
                        <SelectItem value="Equity">{_("Equity")}</SelectItem>
                        <SelectItem value="Income">{_("Income")}</SelectItem>
                        <SelectItem value="Expense">{_("Expense")}</SelectItem>
                    </SelectContent>
                </Select>
            </div>

            {isLoading ? (
                <div className="flex items-center justify-center p-16"><Loader2Icon className="size-6 animate-spin text-muted-foreground" /></div>
            ) : (
                <div className="border rounded-lg overflow-hidden">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>{_("Name")}</TableHead>
                                <TableHead>{_("Number")}</TableHead>
                                <TableHead>{_("Type")}</TableHead>
                                <TableHead>{_("Root Type")}</TableHead>
                                <TableHead>{_("Report")}</TableHead>
                                <TableHead>{_("Currency")}</TableHead>
                                <TableHead>{_("Group")}</TableHead>
                                <TableHead>{_("Disabled")}</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {filtered.map(row => (
                                <TableRow key={row.name}>
                                    <TableCell className="font-medium">{row.account_name}</TableCell>
                                    <TableCell className="text-muted-foreground text-sm">{row.account_number || "-"}</TableCell>
                                    <TableCell>{_(row.account_type)}</TableCell>
                                    <TableCell>{_(row.root_type)}</TableCell>
                                    <TableCell>{_(row.report_type)}</TableCell>
                                    <TableCell>{row.account_currency}</TableCell>
                                    <TableCell>{row.is_group ? _("Yes") : _("No")}</TableCell>
                                    <TableCell>{row.disabled ? _("Yes") : _("No")}</TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </div>
            )}
        </div>
    )
}

export default ChartOfAccounts
