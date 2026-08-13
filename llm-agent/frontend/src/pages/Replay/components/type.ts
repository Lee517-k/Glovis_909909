export interface AgentProfile {
    id: string;
    name: string;
    profile?: { [key: string]: string | number };
}

export interface AgentStatus {
    id: string;
    day: number;
    t: number;
    lng: number;
    lat: number;
    parent_id: number;
    action: string;
    status: { [key: string]: string | number };
}

export interface AgentDialog {
    id: string;
    day: number;
    t: number;
    type: 0 | 1 | 2;
    speaker: string;
    content: string;
}

export interface AgentSurvey {
    id: string;
    day: number;
    t: number;
    survey_id: string;
    result: { [key: string]: string | number };
}

export interface Agent extends AgentProfile, AgentStatus { }

export interface Time {
    day: number;
    t: number;
    step?: number;
}

export interface LngLat {
    lng: number;
    lat: number;
}

export interface CompanyRecord {
    source: number;
    content: {
        from: number | string;
        content: string;
        type: string;
        timestamp: number;
        day: number;
        t: number;
        detailed_inquiry_text?: string;
        expected_products?: string;
        expected_quantity?: string;
    };
}

export interface CompanyData {
    step: number;
    id: number;
    company_name: string;
    company_products: Array<{
        product_name: string;
        product_id: number;
        base_price: number;
        sell_price: number;
        inventory: number;
        is_terminal_product: boolean;
        product_type: string;
        product_construct: string;
        manufacturing_cost: number;
        profit_margin: number;
        consumption_rate: Record<string, any>;
        related_materials: Array<any>;
    }>;
    company_fund: number;
    product_stocks: Array<{
        name: string;
        stock: number;
    }>;
    available_materials: Array<{
        material_name: string;
        material_id: number;
    }>;
    transaction_list: string | Array<any>;
    record: Array<CompanyRecord>;
}
